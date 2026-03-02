#!/usr/bin/env python3
from meshtastic_imports import load_meshtastic_protos

if __name__ == "__main__":
    portnums_pb2, telemetry_pb2 = load_meshtastic_protos()
    print("OK: import riuscito")
    print("PortNum has TELEMETRY_APP:", hasattr(portnums_pb2.PortNum, "TELEMETRY_APP"))
    print("Telemetry message:", telemetry_pb2.Telemetry)