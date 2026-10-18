"""
Gráficas de la tarea (matplotlib, sin interfaz gráfica).

  * `plot_capacity_vs_fo`   -> punto 2.1  (capacidad instalada vs FO)
  * `plot_demand`           -> punto 2.2  (demanda original vs demanda con BESS)
  * `plot_grid_comparison`  -> punto 2.3  (con y sin red)
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from pandas import DataFrame  # noqa: E402

from .experiments import SweepResult  # noqa: E402

C_FO, C_TARGET, C_C0, C_FINAL = "#1f4e79", "#c0392b", "#7f8c8d", "#27ae60"
C_CURT, C_CH, C_DIS = "#e67e22", "#2980b9", "#27ae60"


def _es(x: float, d: int = 0) -> str:
    """Número en formato español: punto de miles y coma decimal (4.128 ; 21,77)."""
    return f"{x:,.{d}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def _save(fig, path: Path) -> Path:
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path


# --------------------------------------------------------------------------
# 2.1  Capacidad instalada vs función objetivo
# --------------------------------------------------------------------------
def plot_capacity_vs_fo(sweep: SweepResult, initial_capacity: float, path: Path) -> Path:
    t = sweep.table
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9.5, 8.5), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 2]})

    # Panel superior: FO
    ax1.plot(t["capacidad_MWh"], t["FO"] / 1e6, "o-", color=C_FO, lw=2, ms=6, label="FO (con red)")
    ax1.axhline(sweep.target_fo / 1e6, ls="--", color=C_TARGET, lw=1.5,
                label=f"50 % de la FO sin baterías ({_es(sweep.target_fo / 1e6, 2)} M$)")
    ax1.scatter([0], [sweep.base_fo / 1e6], s=90, color="black", zorder=5, label="Sin baterías")
    ax1.axvline(initial_capacity, ls=":", color=C_C0, lw=1.5)
    ymin, ymax = ax1.get_ylim()
    ax1.text(initial_capacity, ymax - 0.03 * (ymax - ymin), f" C₀ = {_es(initial_capacity)} MWh",
             color=C_C0, va="top", ha="left", fontsize=9)
    if sweep.reached:
        fo_final = t.loc[np.isclose(t["capacidad_MWh"], sweep.final_capacity), "FO"].iloc[0]
        ax1.scatter([sweep.final_capacity], [fo_final / 1e6], s=130, color=C_FINAL, zorder=6,
                    label=f"Capacidad final = {_es(sweep.final_capacity)} MWh")
    ax1.set_ylabel("Función objetivo [millones de $]")
    ax1.set_title("Capacidad instalada de baterías vs función objetivo (24 h)")
    ax1.grid(alpha=0.3)
    ax1.legend(loc="upper right", fontsize=9)

    # Panel inferior: qué cambia en la operación
    ax2.plot(t["capacidad_MWh"], t["vertimiento_MWh"], "o-", color=C_CURT, label="Vertimiento eólico")
    ax2.plot(t["capacidad_MWh"], t["carga_MWh"], "s--", color=C_CH, label="Energía cargada")
    ax2.plot(t["capacidad_MWh"], t["descarga_MWh"], "^--", color=C_DIS, label="Energía descargada")
    ax2.axvline(initial_capacity, ls=":", color=C_C0, lw=1.5)
    ax2.set_xlabel("Capacidad instalada total de baterías [MWh]")
    ax2.set_ylabel("Energía en 24 h [MWh]")
    ax2.grid(alpha=0.3)
    ax2.legend(loc="lower right", fontsize=9)
    return _save(fig, path)


# --------------------------------------------------------------------------
# 2.2  Demanda original vs demanda afectada por las baterías
# --------------------------------------------------------------------------
def plot_demand(h: DataFrame, capacity: float, path: Path, h_base: DataFrame | None = None) -> Path:
    hours = np.arange(1, len(h) + 1)
    orig, net = h["demanda_MW"].to_numpy(), h["demanda_con_BESS_MW"].to_numpy()

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8.5), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 2]})

    ax1.plot(hours, orig, color="black", lw=2.2, label="Demanda original")
    ax1.plot(hours, net, color=C_CH, lw=2.2, ls="--", label="Demanda + carga − descarga")
    ax1.fill_between(hours, orig, net, where=net >= orig, color=C_CH, alpha=0.30, interpolate=True,
                     label="Baterías cargando (suben la demanda)")
    ax1.fill_between(hours, orig, net, where=net < orig, color=C_DIS, alpha=0.35, interpolate=True,
                     label="Baterías descargando (bajan la demanda)")
    ax1.set_ylabel("Potencia [MW]")
    ax1.set_title(f"Demanda original vs demanda con afectación de las baterías ({_es(capacity)} MWh)")
    ax1.grid(alpha=0.3)
    ax1.legend(loc="upper left", fontsize=9)

    # Panel inferior: carga/descarga y vertimiento evitado
    ax2.bar(hours, h["carga_MW"], color=C_CH, alpha=0.8, label="Carga")
    ax2.bar(hours, -h["descarga_MW"], color=C_DIS, alpha=0.8, label="Descarga")
    ax2.axhline(0, color="black", lw=0.8)
    ax2.set_ylabel("Carga (+) / descarga (−) [MW]")
    ax2.set_xlabel("Hora")
    ax2.set_xticks(hours)
    ax2.grid(alpha=0.3)
    handles, labels = ax2.get_legend_handles_labels()

    ax3 = ax2.twinx()
    if h_base is not None:
        ax3.plot(hours, h_base["vertimiento_MW"], color=C_CURT, ls=":", lw=2, label="Vertimiento sin baterías")
    ax3.plot(hours, h["vertimiento_MW"], color=C_CURT, lw=2, label="Vertimiento con baterías")
    ax3.set_ylabel("Vertimiento eólico [MW]", color=C_CURT)
    h3, l3 = ax3.get_legend_handles_labels()
    ax2.legend(handles + h3, labels + l3, loc="upper center", bbox_to_anchor=(0.5, -0.17),
               fontsize=9, ncol=4, frameon=False)
    return _save(fig, path)


# --------------------------------------------------------------------------
# 2.3  Con y sin red
# --------------------------------------------------------------------------
def plot_grid_comparison(table: DataFrame, path: Path) -> Path:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5), gridspec_kw={"width_ratios": [3, 2]})

    # Panel izquierdo: FO por caso
    groups = [("Sin baterías", False),
              (f"Con baterías ({_es(table.loc[table['con_BESS'], 'bess_MWh'].iloc[0])} MWh)", True)]
    x = np.arange(len(groups))
    w = 0.36
    for k, (label, offset, color) in enumerate([("Con red", -w / 2, C_FO), ("Sin red (uninodal)", w / 2, "#95a5a6")]):
        vals = [table[(table["con_BESS"] == b) & (table["con_red"] == (k == 0))]["FO"].iloc[0] / 1e6
                for _, b in groups]
        bars = ax1.bar(x + offset, vals, w, color=color, label=label)
        for r, v in zip(bars, vals):
            ax1.text(r.get_x() + r.get_width() / 2, v, _es(v, 3), ha="center", va="bottom", fontsize=8)
    ax1.set_xticks(x)
    ax1.set_xticklabels([g[0] for g in groups])
    ax1.set_ylabel("Función objetivo [millones de $]")
    ax1.set_title("FO con y sin red")
    ax1.set_ylim(0, ax1.get_ylim()[1] * 1.12)
    ax1.grid(axis="y", alpha=0.3)
    ax1.legend(fontsize=9)

    # Panel derecho: carga máxima de las líneas en los casos con red
    nodal = table[table["con_red"]]
    ax2.bar(range(len(nodal)), nodal["max_carga_linea_pct"], color=C_FO, width=0.5)
    for i, v in enumerate(nodal["max_carga_linea_pct"]):
        ax2.text(i, v, f"{_es(v, 1)} %", ha="center", va="bottom", fontsize=9)
    ax2.axhline(100, color=C_TARGET, ls="--", label="Capacidad de la línea")
    ax2.set_xticks(range(len(nodal)))
    ax2.set_xticklabels(["Sin baterías", "Con baterías"])
    ax2.set_ylim(0, 128)
    ax2.set_ylabel("Carga máxima de una línea [% de su capacidad]")
    ax2.set_title("¿Se congestiona la red?")
    ax2.grid(axis="y", alpha=0.3)
    ax2.legend(fontsize=9, loc="upper left")
    return _save(fig, path)
