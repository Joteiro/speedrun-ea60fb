"""
Agrega una corrida importada (vía Hooksy/Pipedream) a imported_runs.json,
evitando duplicados. Lo dispara el workflow ingest.yml con los datos que
manda Pipedream en client_payload (via variables de entorno).

Deduplica por 'start' (el timestamp de inicio identifica la corrida).
"""
import json
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent
IMPORTED_PATH = BASE / "imported_runs.json"


def main():
    date = os.environ.get("RUN_DATE", "").strip()
    if not date:
        raise SystemExit("Falta RUN_DATE")
    start = os.environ.get("RUN_START", "").strip()
    end = os.environ.get("RUN_END", "").strip()
    dist = os.environ.get("RUN_DIST", "").strip()
    ritmo = os.environ.get("RUN_RITMO", "").strip() or None
    fc = os.environ.get("RUN_FC", "").strip()

    entry = {
        "date": date,
        "dist": round(float(dist), 2) if dist else None,
        "ritmo": ritmo,
        "fc": int(float(fc)) if fc else None,
        "start": start or None,
        "end": end or None,
    }

    data = json.loads(IMPORTED_PATH.read_text(encoding="utf-8")) if IMPORTED_PATH.exists() else []
    key = start or f"{date}|{dist}"
    for e in data:
        if (e.get("start") or f"{e.get('date')}|{e.get('dist')}") == key:
            print(f"Ya existe, no se agrega: {key}")
            return

    data.append(entry)
    data.sort(key=lambda e: e.get("start") or e.get("date"))
    IMPORTED_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Corrida importada agregada: {entry}")


if __name__ == "__main__":
    main()
