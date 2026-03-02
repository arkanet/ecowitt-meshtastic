# meshtastic_imports.py
# Scopo: normalizzare gli import protobuf Meshtastic tra versioni diverse.

def load_meshtastic_protos():
    errors = []

    # Variante 1 (molto comune)
    try:
        from meshtastic import portnums_pb2, telemetry_pb2
        return portnums_pb2, telemetry_pb2
    except Exception as e:
        errors.append(("from meshtastic import portnums_pb2, telemetry_pb2", str(e)))

    # Variante 2
    try:
        import meshtastic.portnums_pb2 as portnums_pb2
        import meshtastic.telemetry_pb2 as telemetry_pb2
        return portnums_pb2, telemetry_pb2
    except Exception as e:
        errors.append(("import meshtastic.portnums_pb2 / telemetry_pb2", str(e)))

    # Variante 3 
    try:
        from meshtastic.protobuf import portnums_pb2, telemetry_pb2
        return portnums_pb2, telemetry_pb2
    except Exception as e:
        errors.append(("from meshtastic.protobuf import portnums_pb2, telemetry_pb2", str(e)))

    # Variante 4 
    try:
        from meshtastic import portnums_pb2
        from meshtastic.protobuf import telemetry_pb2
        return portnums_pb2, telemetry_pb2
    except Exception as e:
        errors.append(("from meshtastic import portnums_pb2; from meshtastic.protobuf import telemetry_pb2", str(e)))

    # Variante 5 
    try:
        from meshtastic.protobuf import portnums_pb2
        from meshtastic import telemetry_pb2
        return portnums_pb2, telemetry_pb2
    except Exception as e:
        errors.append(("from meshtastic.protobuf import portnums_pb2; from meshtastic import telemetry_pb2", str(e)))

    # Fallimento totale: stampa tentativi
    msg = ["Impossibile importare i protobuf Meshtastic. Tentativi fatti:"]
    for imp, err in errors:
        msg.append(f"- {imp}  =>  {err}")
    raise ImportError("\n".join(msg))