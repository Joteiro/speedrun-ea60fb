"""
Analiza data/runs.csv y genera graficos de evolucion para seguir el plan
de cara a la Zara Athleticz Speed Run.

Uso:
    python 3_analyze.py
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"


def fmt_pace(sec):
    if pd.isna(sec):
        return ""
    m, s = divmod(int(round(sec)), 60)
    return f"{m}:{s:02d}"


def main():
    csv = DATA / "runs.csv"
    if not csv.exists():
        print("Falta data/runs.csv. Ejecuta primero: python 2_fetch.py")
        return

    df = pd.read_csv(csv, parse_dates=["fecha"]).sort_values("fecha")

    # Oura no tiene GPS: filtramos salidas con ritmo/distancia plausibles
    # para que los graficos de ritmo no se distorsionen con datos basura.
    valido = (
        (df["distancia_km"] >= 2.0)
        & (df["ritmo_s_km"].between(240, 600))  # entre 4:00 y 10:00 /km
    )
    df_pace = df[valido].copy()
    print(f"Salidas con ritmo plausible (GPS-like): {len(df_pace)} de {len(df)}")

    # --- Metricas resumen ---
    print("=" * 55)
    print(f"RESUMEN  ({len(df)} runnings)")
    print("=" * 55)
    print(f"Km totales (validos): {df_pace['distancia_km'].sum():.1f} km")
    if len(df_pace):
        print(f"Ritmo medio:       {fmt_pace(df_pace['ritmo_s_km'].mean())}/km")
        print(f"Mejor ritmo:       {fmt_pace(df_pace['ritmo_s_km'].min())}/km")
    print(f"FC media global:   {df['fc_media'].mean():.0f} ppm  "
          f"(dato fiable de Oura)")
    print(f"FC max registrada: {df['fc_max'].max():.0f} ppm")

    # --- Graficos ---
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    fig.suptitle("Evolucion running — camino a la Zara Speed Run", fontsize=14)

    # 1) Ritmo en el tiempo (invertido: mas arriba = mas rapido)
    ax = axes[0, 0]
    ax.plot(df_pace["fecha"], df_pace["ritmo_s_km"], "o-", color="#d1495b")
    ax.invert_yaxis()
    ax.set_title("Ritmo por salida (solo GPS-like fiables)")
    ax.set_ylabel("min/km")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: fmt_pace(v)))
    ax.axhline(300, ls="--", color="gray", alpha=.6)  # objetivo 5:00/km
    ax.text(0.02, 0.05, "linea gris = objetivo 5:00/km",
            transform=ax.transAxes, fontsize=8, color="gray")
    ax.grid(alpha=.3)

    # 2) Distancia por salida
    ax = axes[0, 1]
    ax.bar(df_pace["fecha"], df_pace["distancia_km"], color="#66a182", width=3)
    ax.set_title("Distancia por salida")
    ax.set_ylabel("km")
    ax.grid(alpha=.3, axis="y")

    # 3) FC media por salida
    ax = axes[1, 0]
    if df["fc_media"].notna().any():
        ax.plot(df["fecha"], df["fc_media"], "o-", color="#e07a5f")
        ax.set_ylabel("ppm")
    ax.set_title("FC media por salida")
    ax.grid(alpha=.3)

    # 4) Eficiencia aerobica: FC media vs ritmo (mas abajo-izquierda = mejor)
    ax = axes[1, 1]
    if len(df_pace) and df_pace["fc_media"].notna().any():
        sc = ax.scatter(df_pace["ritmo_s_km"], df_pace["fc_media"],
                        c=df_pace["fecha"].astype("int64"), cmap="viridis", s=60)
        ax.set_xlabel("Ritmo (min/km)")
        ax.set_ylabel("FC media (ppm)")
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: fmt_pace(v)))
        cbar = fig.colorbar(sc, ax=ax)
        cbar.set_ticks([])
        cbar.set_label("mas oscuro = mas reciente")
    ax.set_title("Eficiencia aerobica (mismo ritmo, menos FC = mejor)")
    ax.grid(alpha=.3)

    plt.tight_layout()
    out = BASE / "evolucion_running.png"
    plt.savefig(out, dpi=130)
    print(f"\nGrafico guardado: {out}")


if __name__ == "__main__":
    main()
