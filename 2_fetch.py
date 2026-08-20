"""
Descarga todos los workouts de Oura, filtra los runnings, cruza con
frecuencia cardiaca y guarda un CSV limpio en data/runs.csv.

Uso:
    python 2_fetch.py                # desde 2025-01-01 hasta hoy
    python 2_fetch.py 2025-03-01     # desde una fecha custom
"""
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

import oura_client as oc

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Actividades que consideramos "correr"
RUN_ACTIVITIES = {"running", "run", "jogging", "trail_running"}


def fmt_pace(sec_per_km: float) -> str:
    """Segundos/km -> 'm:ss/km'."""
    if not sec_per_km or sec_per_km != sec_per_km:  # NaN
        return ""
    m, s = divmod(int(round(sec_per_km)), 60)
    return f"{m}:{s:02d}/km"


def hr_for_window(start_iso: str, end_iso: str) -> dict:
    """FC media/max en la ventana del workout (endpoint heartrate, 5 min)."""
    try:
        payload = oc.api_get(
            "/usercollection/heartrate",
            {"start_datetime": start_iso, "end_datetime": end_iso},
        )
    except Exception as e:
        print(f"  aviso: no se pudo traer FC ({e})")
        return {"hr_mean": None, "hr_max": None, "hr_n": 0}
    bpms = [d["bpm"] for d in payload["data"] if d.get("bpm")]
    if not bpms:
        return {"hr_mean": None, "hr_max": None, "hr_n": 0}
    return {
        "hr_mean": round(sum(bpms) / len(bpms), 1),
        "hr_max": max(bpms),
        "hr_n": len(bpms),
    }


def main():
    start = sys.argv[1] if len(sys.argv) > 1 else "2025-01-01"
    end = date.today().isoformat()
    print(f"Descargando workouts desde {start} hasta {end}...")

    payload = oc.api_get(
        "/usercollection/workout", {"start_date": start, "end_date": end}
    )
    workouts = payload["data"]
    print(f"Total de workouts: {len(workouts)}")

    runs = [w for w in workouts if (w.get("activity") or "").lower() in RUN_ACTIVITIES]
    print(f"Runnings encontrados: {len(runs)}")
    if not runs:
        print("No hay runnings en ese rango. "
              "Revisa que las actividades esten etiquetadas como 'running' en Oura.")
        return

    rows = []
    for w in sorted(runs, key=lambda x: x["start_datetime"]):
        start_dt = datetime.fromisoformat(w["start_datetime"])
        end_dt = datetime.fromisoformat(w["end_datetime"])
        dur_s = (end_dt - start_dt).total_seconds()
        dist_km = (w.get("distance") or 0) / 1000.0
        pace_s = dur_s / dist_km if dist_km > 0 else None

        print(f"  {w['day']}  {dist_km:.2f} km  ({fmt_pace(pace_s)})  -> FC...")
        hr = hr_for_window(w["start_datetime"], w["end_datetime"])

        rows.append({
            "fecha": w["day"],
            "inicio": start_dt.strftime("%Y-%m-%d %H:%M"),
            "distancia_km": round(dist_km, 2),
            "duracion_min": round(dur_s / 60, 1),
            "ritmo_s_km": round(pace_s, 1) if pace_s else None,
            "ritmo": fmt_pace(pace_s),
            "fc_media": hr["hr_mean"],
            "fc_max": hr["hr_max"],
            "calorias": w.get("calories"),
            "intensidad": w.get("intensity"),
            "fuente": w.get("source"),
            "etiqueta": w.get("label"),
        })

    df = pd.DataFrame(rows)
    out = DATA_DIR / "runs.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\nGuardado: {out}  ({len(df)} runnings)")
    print("\nResumen:")
    with pd.option_context("display.max_columns", None, "display.width", 200):
        print(df[["fecha", "distancia_km", "duracion_min", "ritmo",
                  "fc_media", "fc_max", "intensidad"]].to_string(index=False))


if __name__ == "__main__":
    main()
