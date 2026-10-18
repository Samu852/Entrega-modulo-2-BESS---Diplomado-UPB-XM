"""
Experimentos de la tarea.

  * `Runner`            : construye + resuelve + extrae resultados, con caché.
  * `capacity_sweep`    : punto 2.1 -> barrido de capacidad hasta FO <= 50 % de la FO sin baterías.
  * `grid_comparison`   : punto 2.3 -> con y sin red, con y sin baterías.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, replace

from pandas import DataFrame

from .config import CAPACITY_STEP_MWH, CAPACITY_TOL_MWH, TARGET_RATIO
from .data import Data
from .model import ModelOptions, build_model
from .results import bess_table, hourly, summarize
from .solver import SolverConfig, solve

log = logging.getLogger(__name__)


# ==========================================================================
# Runner con caché
# ==========================================================================
@dataclass
class CaseResult:
    options: ModelOptions
    summary: dict
    hourly: DataFrame
    bess: DataFrame
    optimal: bool
    seconds: float

    @property
    def fo(self) -> float:
        return self.summary["FO"]


class Runner:
    """Resuelve casos y recuerda los ya resueltos (misma opción + mismo solver = mismo resultado)."""

    def __init__(self, data: Data, solver_cfg: SolverConfig = SolverConfig()):
        self.data = data
        self.solver_cfg = solver_cfg
        self._cache: dict[tuple, CaseResult] = {}

    def run(self, opts: ModelOptions, solver_cfg: SolverConfig | None = None) -> CaseResult:
        cfg = solver_cfg or self.solver_cfg
        key = (opts, cfg)
        if key not in self._cache:
            t0 = time.time()
            model = build_model(self.data, opts)
            info = solve(model, cfg)
            self._cache[key] = CaseResult(
                options=opts, summary=summarize(model), hourly=hourly(model), bess=bess_table(model),
                optimal=info["optimal"], seconds=time.time() - t0)
            del model   # liberar memoria: solo guardamos tablas pequeñas
        return self._cache[key]


# ==========================================================================
# Punto 2.1: barrido de capacidad
# ==========================================================================
@dataclass
class SweepResult:
    table: DataFrame            # una fila por capacidad evaluada (ordenada)
    base_fo: float              # FO del sistema sin baterías
    target_fo: float            # TARGET_RATIO * base_fo
    final_capacity: float | None   # menor capacidad evaluada con FO <= target (None si no se alcanzó)

    @property
    def reached(self) -> bool:
        return self.final_capacity is not None


def capacity_sweep(
    runner: Runner,
    initial_capacity: float,
    step: float = CAPACITY_STEP_MWH,
    tol: float = CAPACITY_TOL_MWH,
    target_ratio: float = TARGET_RATIO,
    max_capacity: float | None = None,
    base_options: ModelOptions = ModelOptions(),
) -> SweepResult:
    """Aumenta la capacidad instalada hasta que FO <= `target_ratio` * FO(sin baterías).

    Fase 1 (barrido):   C0, C0+paso, C0+2·paso, ... hasta cruzar el objetivo.
    Fase 2 (bisección): se refina el intervalo del cruce hasta una precisión `tol` [MWh].
    """
    base = runner.run(replace(base_options, use_bess=False, bess_capacity_mwh=None))
    base_fo = base.fo
    target = target_ratio * base_fo
    max_capacity = max_capacity or 20 * runner.data.base_bess_capacity
    log.info("FO sin baterías = %s  ->  objetivo (%.0f %%) = %s",
             f"{base_fo:,.0f}", 100 * target_ratio, f"{target:,.0f}")

    rows = [_row(0.0, base, base_fo, "base (sin BESS)")]

    def evaluate(cap: float, phase: str) -> float:
        opts = replace(base_options, use_bess=True, bess_capacity_mwh=cap)
        res = runner.run(opts)
        rows.append(_row(cap, res, base_fo, phase))
        log.info("  %-10s C = %8.1f MWh  FO = %15s  (%5.1f %% de la base)  [%.1fs]",
                 phase, cap, f"{res.fo:,.0f}", 100 * res.fo / base_fo, res.seconds)
        return res.fo

    # ---- Fase 1: barrido por pasos ---------------------------------------
    cap = float(initial_capacity)
    fo = evaluate(cap, "barrido")
    if fo <= target:
        log.info("La capacidad inicial ya cumple el objetivo.")
        return _finish(rows, base_fo, target, cap)

    lo = cap
    while fo > target:
        lo, cap = cap, cap + step
        if cap > max_capacity:
            log.warning("Se superó la capacidad máxima (%.0f MWh) sin alcanzar el objetivo.", max_capacity)
            return _finish(rows, base_fo, target, None)
        fo = evaluate(cap, "barrido")
    hi = cap

    # ---- Fase 2: bisección en [lo, hi] -----------------------------------
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if evaluate(mid, "bisección") <= target:
            hi = mid
        else:
            lo = mid
    return _finish(rows, base_fo, target, hi)


def _row(cap: float, res: CaseResult, base_fo: float, phase: str) -> dict:
    s = res.summary
    return {
        "capacidad_MWh": cap, "fase": phase, "FO": s["FO"], "FO_pct_base": 100 * s["FO"] / base_fo,
        "costo_termico": s["costo_termico"], "vertimiento_MWh": s["vertimiento_MWh"],
        "costo_vertimiento": s["costo_vertimiento"], "ENS_MWh": s["ENS_MWh"],
        "carga_MWh": s["carga_MWh"], "descarga_MWh": s["descarga_MWh"],
        "energia_inicial_MWh": s["energia_inicial_MWh"], "energia_final_MWh": s["energia_final_MWh"],
        "bess_carga_y_descarga_h": s["bess_carga_y_descarga_h"],
        "optimo": res.optimal, "segundos": res.seconds,
    }


def _finish(rows: list[dict], base_fo: float, target: float, final_cap: float | None) -> SweepResult:
    table = DataFrame(rows).sort_values("capacidad_MWh").reset_index(drop=True)
    # Pérdida marginal de FO entre puntos consecutivos [$ por MWh instalado]
    table["dFO_dCap"] = table["FO"].diff() / table["capacidad_MWh"].diff()
    return SweepResult(table=table, base_fo=base_fo, target_fo=target, final_capacity=final_cap)


# ==========================================================================
# Punto 2.3: con y sin red
# ==========================================================================
def grid_comparison(
    runner: Runner,
    capacity: float,
    solver_cfg: SolverConfig | None = None,
    base_options: ModelOptions = ModelOptions(),
) -> DataFrame:
    """FO con/sin red (barra única) para el sistema sin baterías y con `capacity` MWh."""
    cases = []
    for use_bess in (False, True):
        for uninodal in (False, True):
            opts = replace(base_options, uninodal=uninodal, use_bess=use_bess,
                           bess_capacity_mwh=capacity if use_bess else None)
            res = runner.run(opts, solver_cfg)
            s = res.summary
            log.info("  %-28s FO = %s  [%.1fs]", opts.label, f"{s['FO']:,.2f}", res.seconds)
            cases.append({
                "caso": opts.label, "con_red": not uninodal, "con_BESS": use_bess,
                "bess_MWh": capacity if use_bess else 0.0, "FO": s["FO"],
                "costo_termico": s["costo_termico"], "vertimiento_MWh": s["vertimiento_MWh"],
                "ENS_MWh": s["ENS_MWh"], "max_carga_linea_pct": s["max_carga_linea_pct"],
                "lineas_congestionadas_h": s["lineas_congestionadas_h"], "optimo": res.optimal})
    table = DataFrame(cases)

    # Cambio de FO al pasar de "sin red" a "con red" (mismo BESS)
    for use_bess in (False, True):
        sel = table["con_BESS"] == use_bess
        fo_con = table.loc[sel & table["con_red"], "FO"].iloc[0]
        fo_sin = table.loc[sel & ~table["con_red"], "FO"].iloc[0]
        table.loc[sel & table["con_red"], "dFO_vs_sin_red"] = fo_con - fo_sin
        table.loc[sel & table["con_red"], "dFO_vs_sin_red_pct"] = 100 * (fo_con - fo_sin) / fo_sin
    return table
