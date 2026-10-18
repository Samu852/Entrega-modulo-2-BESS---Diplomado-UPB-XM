"""
Extracción de resultados de un modelo ya resuelto.

Solo *lee* el modelo (no lo modifica): devuelve un resumen escalar (`summarize`)
y una tabla horaria (`hourly`) con las series que se grafican en la tarea.
"""
from __future__ import annotations

from pandas import DataFrame
from pyomo.environ import ConcreteModel, value

from .config import VOLL, WS_PENALTY

SIMUL_TOL_MW = 1e-3       # umbral para considerar que una batería carga/descarga
CONGESTION_TOL = 0.999   # una línea se considera congestionada si |flujo| >= 99,9 % de su capacidad


def summarize(m: ConcreteModel) -> dict:
    """Indicadores escalares de la solución (todos los costos en $, energías en MWh)."""
    T, B = list(m.s_periods), list(m.s_bess)
    last = T[-1]

    curt = sum(value(m.v_curt[t, w]) for t in T for w in m.s_wind)
    ens = sum(value(m.v_ll[t, s]) + value(m.v_sl[t, s]) for t in T for s in m.s_buses)

    out = {
        "FO": value(m.e_obj),
        "costo_termico": sum(value(m.v_c[t, i]) for t in T for i in m.s_generators),
        "vertimiento_MWh": curt,
        "costo_vertimiento": curt * WS_PENALTY,
        "ENS_MWh": ens,
        "costo_ENS": ens * VOLL,
        "gen_termica_MWh": sum(value(m.v_g[t, i]) for t in T for i in m.s_generators),
        "arranques": sum(round(value(m.v_y[t, i])) for t in T for i in m.s_generators),
        "bess_MWh": sum(value(m.p_bess_cap[b]) for b in B),
        "carga_MWh": sum(value(m.v_bess_pc[t, b]) for t in T for b in B),
        "descarga_MWh": sum(value(m.v_bess_pd[t, b]) for t in T for b in B),
        "energia_inicial_MWh": sum(value(m.p_bess_soc_ini[b]) * value(m.p_bess_cap[b]) for b in B),
        "energia_final_MWh": sum(value(m.v_bess_soc[last, b]) * value(m.p_bess_cap[b]) for b in B),
        # Diagnóstico de validez: baterías-hora con carga Y descarga a la vez (> 1 kW).
        # Si es > 0 el modelo podría estar "quemando" energía por las pérdidas de eficiencia.
        "bess_carga_y_descarga_h": sum(
            1 for t in T for b in B
            if value(m.v_bess_pc[t, b]) > SIMUL_TOL_MW and value(m.v_bess_pd[t, b]) > SIMUL_TOL_MW),
    }

    # Indicadores de la red (solo si el modelo es multinodal)
    if hasattr(m, "v_pf"):
        loading = [abs(value(m.v_pf[t, l])) / value(m.line_capacity[l]) for t in T for l in m.s_lines]
        out["max_carga_linea_pct"] = 100 * max(loading)
        out["lineas_congestionadas_h"] = sum(1 for x in loading if x >= CONGESTION_TOL)
    else:
        out["max_carga_linea_pct"] = float("nan")
        out["lineas_congestionadas_h"] = float("nan")
    return out


def hourly(m: ConcreteModel) -> DataFrame:
    """Series horarias agregadas del sistema."""
    T, B = list(m.s_periods), list(m.s_bess)

    demanda = [sum(value(m.load_profile[s, t]) for s in m.s_buses) for t in T]
    carga = [sum(value(m.v_bess_pc[t, b]) for b in B) for t in T]
    descarga = [sum(value(m.v_bess_pd[t, b]) for b in B) for t in T]
    energia = [sum(value(m.v_bess_soc[t, b]) * value(m.p_bess_cap[b]) for b in B) for t in T]

    return DataFrame({
        "demanda_MW": demanda,
        "carga_MW": carga,
        "descarga_MW": descarga,
        "demanda_con_BESS_MW": [d + c - g for d, c, g in zip(demanda, carga, descarga)],
        "eolica_disponible_MW": [sum(value(m.wind_profile[w, t]) for w in m.s_wind) for t in T],
        "vertimiento_MW": [sum(value(m.v_curt[t, w]) for w in m.s_wind) for t in T],
        "gen_termica_MW": [sum(value(m.v_g[t, i]) for i in m.s_generators) for t in T],
        "energia_almacenada_MWh": energia,
    }, index=T)


def bess_table(m: ConcreteModel) -> DataFrame:
    """Resumen por batería: barra, capacidad, SOC mínimo/máximo alcanzado y energía cargada/descargada."""
    T = list(m.s_periods)
    rows = []
    for b in m.s_bess:
        soc = [value(m.v_bess_soc[t, b]) for t in T]
        rows.append({
            "bateria": b,
            "barra": next(s for s in m.s_buses if m.t_bess_map[b, s]),
            "capacidad_MWh": value(m.p_bess_cap[b]),
            "soc_inicial_pu": value(m.p_bess_soc_ini[b]),
            "soc_min_pu": min(soc),
            "soc_max_pu": max(soc),
            "carga_MWh": sum(value(m.v_bess_pc[t, b]) for t in T),
            "descarga_MWh": sum(value(m.v_bess_pd[t, b]) for t in T),
        })
    return DataFrame(rows, columns=["bateria", "barra", "capacidad_MWh", "soc_inicial_pu", "soc_min_pu",
                                    "soc_max_pu", "carga_MWh", "descarga_MWh"])
