"""
Regenera el dashboard con datos frescos de Oura y lo publica en GitHub Pages.

Flujo:
  1. Descarga los workouts de los ultimos ~400 dias y filtra runnings.
  2. Cruza cada salida con frecuencia cardiaca (FC media).
  3. Inyecta los datos en dashboard.html -> docs/index.html.
  4. git add / commit / push  (para que GitHub Pages lo sirva).

Uso:
    python build_dashboard.py            # baja datos, regenera y publica
    python build_dashboard.py --no-push  # regenera pero no hace push (prueba)
"""
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import oura_client as oc

BASE = Path(__file__).resolve().parent
TEMPLATE = BASE / "dashboard.html"
DOCS = BASE / "docs"
OUT = DOCS / "index.html"

RUN_ACTIVITIES = {"running", "run", "jogging", "trail_running"}
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul",
         "ago", "sep", "oct", "nov", "dic"]


def fmt_pace(sec_per_km):
    m, s = divmod(int(round(sec_per_km)), 60)
    return f"{m}:{s:02d}"


def hr_mean(start_iso, end_iso):
    try:
        payload = oc.api_get(
            "/usercollection/heartrate",
            {"start_datetime": start_iso, "end_datetime": end_iso},
        )
    except Exception as e:
        print(f"  aviso FC: {e}")
        return None
    bpms = [d["bpm"] for d in payload["data"] if d.get("bpm")]
    return round(sum(bpms) / len(bpms)) if bpms else None


def fetch_runs():
    start = (date.today() - timedelta(days=400)).isoformat()
    end = date.today().isoformat()
    print(f"Descargando workouts {start} -> {end} ...")
    payload = oc.api_get(
        "/usercollection/workout", {"start_date": start, "end_date": end}
    )
    runs = [w for w in payload["data"]
            if (w.get("activity") or "").lower() in RUN_ACTIVITIES]
    print(f"Runnings encontrados: {len(runs)}")

    rows = []
    for w in sorted(runs, key=lambda x: x["start_datetime"]):
        s_dt = datetime.fromisoformat(w["start_datetime"])
        e_dt = datetime.fromisoformat(w["end_datetime"])
        dur_s = (e_dt - s_dt).total_seconds()
        dist_km = (w.get("distance") or 0) / 1000.0
        pace_s = dur_s / dist_km if dist_km > 0 else None

        # ritmo/distancia solo si son plausibles (Oura no tiene GPS)
        plausible = dist_km >= 2.0 and pace_s and 240 <= pace_s <= 600
        fc = hr_mean(w["start_datetime"], w["end_datetime"])
        if fc is None:
            continue  # sin FC no aporta al dashboard

        rows.append({
            "fecha": f"{s_dt.day:02d} {MESES[s_dt.month - 1]}",
            "dist": round(dist_km, 2) if plausible else None,
            "ritmo": fmt_pace(pace_s) if plausible else None,
            "fc": fc,
        })
        print(f"  {rows[-1]['fecha']}  FC {fc}"
              + (f"  {rows[-1]['dist']}km {rows[-1]['ritmo']}/km" if plausible else ""))
    return rows


def js_array(rows):
    def val(x):
        if x is None:
            return "null"
        if isinstance(x, str):
            return f'"{x}"'
        return str(x)
    lines = [
        f'    {{ fecha:{val(r["fecha"])}, dist:{val(r["dist"])}, '
        f'ritmo:{val(r["ritmo"])}, fc:{val(r["fc"])} }},'
        for r in rows
    ]
    return "\n".join(lines)


def build_html(rows):
    html = TEMPLATE.read_text(encoding="utf-8")
    today = date.today()
    data_date = f"{today.day:02d} {MESES[today.month - 1]} {today.year}"
    block = (
        "/* DATA_START — generado por build_dashboard.py, no editar a mano */\n"
        f'  const DATA_DATE = "{data_date}";\n'
        "  const runs = [\n"
        f"{js_array(rows)}\n"
        "  ];\n"
        "  /* DATA_END */"
    )
    new_html, n = re.subn(
        r"/\* DATA_START.*?/\* DATA_END \*/",
        lambda _: block, html, count=1, flags=re.DOTALL,
    )
    if n != 1:
        raise RuntimeError("No se encontro el bloque DATA_START/DATA_END en dashboard.html")
    DOCS.mkdir(exist_ok=True)
    OUT.write_text(new_html, encoding="utf-8")
    print(f"Generado: {OUT}  ({len(rows)} runnings)")


def git_publish():
    def run(*args):
        return subprocess.run(["git", *args], cwd=BASE,
                              capture_output=True, text=True)
    run("add", "docs/index.html", "dashboard.html", "build_dashboard.py",
        ".gitignore", "oura_client.py", "1_authorize.py", "2_fetch.py",
        "3_analyze.py")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    commit = run("commit", "-m", f"Actualizar dashboard ({stamp})")
    if "nothing to commit" in (commit.stdout + commit.stderr):
        print("Sin cambios nuevos, no hay nada que publicar.")
        return
    push = run("push", "origin", "main")
    if push.returncode == 0:
        print("Publicado en GitHub Pages.")
    else:
        print("ERROR al hacer push:\n" + push.stderr)
        print("(El HTML local quedo actualizado igual.)")


def main():
    rows = fetch_runs()
    build_html(rows)
    if "--no-push" not in sys.argv:
        git_publish()
    else:
        print("(--no-push: no se publico)")


if __name__ == "__main__":
    main()
