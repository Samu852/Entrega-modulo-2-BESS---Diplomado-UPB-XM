"""
Tarea Módulo 2 - Diplomado UPB-XM
Unit Commitment (IEEE 24 barras) con sistemas de almacenamiento en baterías (BESS).

Ejecuta de principio a fin los puntos 2.1, 2.2 y 2.3 de la tarea:

  2.1  Barrido de capacidad instalada hasta FO <= 50 % de la FO sin baterías
       -> gráfica capacidad instalada vs FO
  2.2  Demanda original vs demanda con baterías (demanda + carga - descarga)
  2.3  Con la capacidad de 2.1, corrida con red y sin red -> cambio en la FO

Uso:
    python main.py --cedula 1234500222        # capacidad inicial = suma de ternas
    python main.py --capacidad 957            # o directamente en MWh
    python main.py --cedula 1234500222 --paso 100 --tol 5
"""
from __future__ import annotations

import argparse
import logging
from dataclasses import replace
from pathlib import Path

from bess_uc.config import (CAPACITY_STEP_MWH, CAPACITY_TOL_MWH, DATA_PATH, N_PERIODS, RESULTS_DIR,
                            TARGET_RATIO, VOLL, WS_PENALTY, initial_capacity_from_cedula)
from bess_uc.data import Data
from bess_uc.experiments import Runner, capacity_sweep, grid_comparison
from bess_uc.model import ModelOptions
from bess_uc.plots import plot_capacity_vs_fo, plot_demand, plot_grid_comparison
from bess_uc.report import export_excel, write_summary
from bess_uc.solver import SolverConfig

log = logging.getLogger("tarea")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--cedula", help="Número de cédula (se calcula la capacidad inicial)")
    g.add_argument("--capacidad", type=float, help="Capacidad inicial en MWh (alternativa a --cedula)")

    p.add_argument("--paso", type=float, default=CAPACITY_STEP_MWH, help="Incremento del barrido [MWh]")
    p.add_argument("--tol", type=float, default=CAPACITY_TOL_MWH, help="Precisión de la capacidad final [MWh]")
    p.add_argument("--objetivo", type=float, default=TARGET_RATIO, help="Fracción de la FO sin baterías (0.5 = mitad)")
    p.add_argument("--gap", type=float, default=1e-4, help="MIP gap del barrido (2.1)")
    p.add_argument("--gap-red", type=float, default=1e-5, help="MIP gap de la comparación con/sin red (2.3)")
    p.add_argument("--time-limit", type=float, default=900, help="Segundos máximos por corrida")
    p.add_argument("--periodos", type=int, default=N_PERIODS, help="Horas del horizonte")
    p.add_argument("--excel", type=Path, default=DATA_PATH, help="Archivo de datos")
    p.add_argument("--salida", type=Path, default=RESULTS_DIR, help="Carpeta de resultados")

    # Opciones del modelo
    p.add_argument("--carga-original", action="store_true",
                   help="Reproduce el modelo original del profesor (límite de carga con pd en vez de pc)")
    p.add_argument("--potencia-fija", action="store_true",
                   help="Solo escala la energía (MWh); la potencia pd/pc se mantiene")
    p.add_argument("--soc-final", action="store_true",
                   help="Extensión: exige SOC final >= inicial (E24)")
    p.add_argument("--tee", action="store_true", help="Mostrar el log del solver")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s", datefmt="%H:%M:%S")
    out: Path = args.salida
    out.mkdir(parents=True, exist_ok=True)

    c0 = args.capacidad if args.capacidad is not None else initial_capacity_from_cedula(args.cedula)
    log.info("Capacidad inicial C0 = %s MWh", f"{c0:,.0f}")

    data = Data(args.excel, max_periods=args.periodos)
    sweep_cfg = SolverConfig(time_limit=args.time_limit, mip_gap=args.gap, tee=args.tee)
    grid_cfg = SolverConfig(time_limit=args.time_limit, mip_gap=args.gap_red, tee=args.tee)
    runner = Runner(data, sweep_cfg)
    base_opts = ModelOptions(charge_limit="pd" if args.carga_original else "pc",
                             scale_power=not args.potencia_fija, terminal_soc=args.soc_final)

    # ---------------- 2.1 ----------------------------------------------------
    log.info("=== 2.1 Barrido de capacidad ===")
    sweep = capacity_sweep(runner, c0, step=args.paso, tol=args.tol,
                           target_ratio=args.objetivo, base_options=base_opts)
    plot_capacity_vs_fo(sweep, c0, out / "fig_2_1_capacidad_vs_FO.png")
    if not sweep.reached:
        log.error("No se alcanzó el objetivo; revisa --paso o los datos. Se guarda lo calculado.")
        sweep.table.to_csv(out / "barrido_capacidad.csv", index=False)
        return
    c_final = sweep.final_capacity
    log.info("Capacidad final (FO <= %.0f %% de la base) = %.1f MWh", 100 * args.objetivo, c_final)

    # ---------------- 2.2 ----------------------------------------------------
    log.info("=== 2.2 Demanda original vs demanda con BESS ===")
    final = runner.run(replace(base_opts, use_bess=True, bess_capacity_mwh=c_final))
    base = runner.run(replace(base_opts, use_bess=False))
    plot_demand(final.hourly, c_final, out / "fig_2_2_demanda_original_vs_con_BESS.png", base.hourly)

    # ---------------- 2.3 ----------------------------------------------------
    log.info("=== 2.3 Con y sin red (gap %.0e) ===", args.gap_red)
    grid = grid_comparison(runner, c_final, grid_cfg, base_options=base_opts)
    plot_grid_comparison(grid, out / "fig_2_3_con_y_sin_red.png")

    # ---------------- Salidas ------------------------------------------------
    params = {
        "Capacidad inicial C0 [MWh]": f"{c0:,.0f}",
        "Cédula": args.cedula or "(capacidad dada directamente)",
        "Horizonte [h]": args.periodos,
        "Paso del barrido [MWh]": args.paso, "Tolerancia [MWh]": args.tol,
        "Objetivo [fracción de FO base]": args.objetivo,
        "MIP gap barrido / red": f"{args.gap:g} / {args.gap_red:g}",
        "Límite de carga": "pd (original)" if args.carga_original else "pc (corregido)",
        "Potencia escalada con la capacidad": not args.potencia_fija,
        "SOC final >= inicial": args.soc_final,
        "Penalización vertimiento [$/MWh]": f"{WS_PENALTY:,.0f}", "VOLL [$/MWh]": f"{VOLL:,.0f}",
    }
    sweep.table.to_csv(out / "barrido_capacidad.csv", index=False)
    grid.to_csv(out / "comparacion_red.csv", index=False)
    final.hourly.to_csv(out / "horario_con_BESS.csv", index_label="periodo")
    export_excel(out / "resultados.xlsx", params, sweep, final, base, grid)
    write_summary(out / "resumen.md", params, sweep, final, base, grid)

    log.info("=== LISTO === Resultados en: %s", out.resolve())
    log.info("FO sin baterías : %15s", f"{sweep.base_fo:,.0f}")
    log.info("FO con %6.0f MWh: %15s (%.2f %% de la base)", c_final, f"{final.fo:,.0f}", 100 * final.fo / sweep.base_fo)


if __name__ == "__main__":
    main()
