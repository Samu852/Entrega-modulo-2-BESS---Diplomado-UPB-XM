"""
Llamado al solver (HiGHS vía Pyomo) con manejo explícito del estado de la solución.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from pyomo.environ import ConcreteModel, SolverFactory, SolverStatus, TerminationCondition, value

log = logging.getLogger(__name__)


class SolveError(RuntimeError):
    """El solver no encontró ninguna solución utilizable."""


@dataclass(frozen=True)
class SolverConfig:
    name: str = "highs"
    time_limit: float = 900.0   # segundos por corrida
    mip_gap: float = 1e-4       # gap relativo (igual al valor por defecto de HiGHS)
    tee: bool = False           # True = imprimir el log del solver


def solve(m: ConcreteModel, cfg: SolverConfig = SolverConfig()) -> dict:
    """Resuelve el modelo y devuelve {'fo', 'status', 'termination', 'optimal'}.

    * Óptimo (dentro del gap) -> `optimal=True`.
    * Límite de tiempo con solución factible -> `optimal=False` y se advierte.
    * Cualquier otro caso -> `SolveError`.
    """
    solver = SolverFactory(cfg.name)
    results = solver.solve(
        m, tee=cfg.tee, load_solutions=False,
        options={"time_limit": cfg.time_limit, "mip_rel_gap": cfg.mip_gap})

    status = results.solver.status
    term = results.solver.termination_condition
    optimal = status == SolverStatus.ok and term == TerminationCondition.optimal
    time_limit_hit = term == TerminationCondition.maxTimeLimit

    if not (optimal or time_limit_hit) or len(results.solution) == 0:
        raise SolveError(f"Sin solución utilizable: status={status}, terminación={term}")

    m.solutions.load_from(results)
    if time_limit_hit:
        log.warning("Se alcanzó el límite de tiempo; se usa la mejor solución factible "
                    "(la FO puede no ser óptima).")

    return {"fo": value(m.e_obj), "status": str(status), "termination": str(term), "optimal": optimal}
