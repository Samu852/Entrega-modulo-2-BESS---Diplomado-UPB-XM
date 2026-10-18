"""
Modelo de Unit Commitment (IEEE-24) con sistemas de almacenamiento (BESS).

Basado en `C03/bess.py` del curso. Se conserva la nomenclatura del profesor
(`s_` conjuntos, `p_`/`t_` parámetros, `v_` variables, `e_` ecuaciones) para
que sea directo compararlo. Las ecuaciones están numeradas (E1, E2, ...) igual
que en `docs/modelo_bess.md`.

Diferencias respecto al original (todas controladas por `ModelOptions`):
  * El modelo se construye dentro de `build_model()`, así se puede resolver
    muchas veces cambiando la capacidad de baterías o activando/quitando la red.
  * `charge_limit="pc"` corrige un error del original: la restricción de
    potencia máxima de CARGA usaba la potencia de DESCARGA (`p_bess_pd`).
    Con `charge_limit="pd"` se reproduce exactamente el comportamiento original.
  * `terminal_soc=True` (opcional, apagado por defecto) agrega E24: la energía
    final almacenada no puede ser menor que la inicial.
  * Sin baterías el conjunto `s_bess` queda vacío (no hay que "fijar a cero").
  * En modo uninodal no se crean las variables de flujo ni de ángulo.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import pi

from pyomo.environ import (
    Binary, ConcreteModel, Constraint, NonNegativeReals, Objective, Param,
    Reals, Set, Var, minimize,
)

from .config import REF_BUS, VOLL, WS_PENALTY
from .data import Data


# ==========================================================================
# Opciones del modelo
# ==========================================================================
@dataclass(frozen=True)
class ModelOptions:
    """Configuración de una corrida (inmutable, por eso sirve como llave de caché)."""

    uninodal: bool = False                   # True = sin red (barra única)
    use_bess: bool = True                    # False = sistema sin baterías
    bess_capacity_mwh: float | None = None   # None = capacidad de los datos
    scale_power: bool = True                 # escalar pd/pc junto con Cap
    charge_limit: str = "pc"                 # "pc" (corregido) | "pd" (original)
    terminal_soc: bool = False               # E24 opcional

    def __post_init__(self):
        if self.charge_limit not in ("pc", "pd"):
            raise ValueError("charge_limit debe ser 'pc' o 'pd'")

    @property
    def label(self) -> str:
        red = "sin red" if self.uninodal else "con red"
        if not self.use_bess:
            return f"{red}, sin BESS"
        cap = "datos" if self.bess_capacity_mwh is None else f"{self.bess_capacity_mwh:,.0f} MWh"
        return f"{red}, BESS {cap}"


# ==========================================================================
# Construcción del modelo
# ==========================================================================
def build_model(data: Data, opts: ModelOptions = ModelOptions()) -> ConcreteModel:
    """Arma el modelo Pyomo completo según `opts`."""
    m = ConcreteModel(name="UC_BESS")
    m.options = opts

    bess = _select_bess(data, opts)

    _add_sets(m, data, bess)
    _add_generator_parameters(m, data)
    _add_network_parameters(m, data)
    _add_bess_parameters(m, bess)
    _add_variables(m, opts)
    _add_objective_and_costs(m)
    _add_commitment_constraints(m)
    _add_ramp_constraints(m)
    _add_balance_constraints(m, opts)
    if not opts.uninodal:
        _add_network_constraints(m)
    _add_bess_constraints(m, opts)
    return m


def _select_bess(data: Data, opts: ModelOptions):
    """Tabla de baterías a usar: vacía, original o escalada."""
    if not opts.use_bess:
        return data.bess_base.iloc[0:0]
    if opts.bess_capacity_mwh is None:
        return data.bess_base
    return data.scaled_bess(opts.bess_capacity_mwh, opts.scale_power)


# --------------------------------------------------------------------------
# Conjuntos
# --------------------------------------------------------------------------
def _add_sets(m: ConcreteModel, data: Data, bess) -> None:
    m.s_buses = Set(initialize=data.s_bus, doc="Barras")
    m.s_periods = Set(initialize=data.s_periods, ordered=True, doc="Periodos (horas)")
    m.s_generators = Set(initialize=data.s_generators, doc="Generadores térmicos")
    m.s_blocks = Set(initialize=data.s_blocks, doc="Bloques de la curva de generación")
    m.s_segments = Set(initialize=data.s_segments, doc="Segmentos del costo de arranque")
    m.s_lines = Set(initialize=data.s_lines, doc="Líneas de transmisión")
    m.s_wind = Set(initialize=data.s_wind, doc="Parques eólicos")
    m.s_bess = Set(initialize=list(bess.index), doc="Baterías (BESS)")


# --------------------------------------------------------------------------
# Parámetros
# --------------------------------------------------------------------------
def _add_generator_parameters(m: ConcreteModel, data: Data) -> None:
    G = data.generators
    gens = m.s_generators

    m.p_count_on = Param(gens, initialize=G["cON"].to_dict(), doc="Horas encendido al inicio")
    m.p_count_off = Param(gens, initialize=G["cOFF"].to_dict(), doc="Horas apagado al inicio")
    m.p_gen_ur = Param(gens, initialize=G["UR"].to_dict(), doc="Rampa de subida [MW/h]")
    m.p_gen_dr = Param(gens, initialize=G["DR"].to_dict(), doc="Rampa de bajada [MW/h]")
    m.p_tmfl = Param(gens, initialize=G["TMFL"].to_dict(), doc="Tiempo mínimo apagado [h]")
    m.p_tmg = Param(gens, initialize=G["TMG"].to_dict(), doc="Tiempo mínimo encendido [h]")
    m.p_mt = Param(gens, initialize=G["MT"].to_dict(), doc="Mínimo técnico [MW]")
    m.p_g_init = Param(gens, initialize=G["G0"].to_dict(), doc="Generación inicial [MW]")
    m.p_co_cost = Param(gens, initialize=G["C0"].to_dict(), doc="Costo fijo de operación [$/h]")

    # Estado inicial: encendido si lleva horas on y generaba algo
    m.p_init_onoff = Param(
        gens, doc="Estado inicial (1 = encendido)",
        initialize=lambda mo, g: 1 if (mo.p_count_on[g] > 0 and mo.p_g_init[g] > 0) else 0)

    # Horas iniciales que obligatoriamente se mantiene el estado inicial
    m.p_l_up_min = Param(
        gens, initialize=lambda mo, g: min(
            len(mo.s_periods),
            max(0, mo.p_tmg[g] - mo.p_count_on[g]) if mo.p_init_onoff[g] else 0))
    m.p_l_down_min = Param(
        gens, initialize=lambda mo, g: min(
            len(mo.s_periods),
            max(0, mo.p_tmfl[g] + mo.p_count_off[g]) if not mo.p_init_onoff[g] else 0))

    m.t_gen_map = Param(gens, m.s_buses, doc="1 si el generador está en la barra",
                        initialize=lambda _, g, s: 1 if G.loc[g, "bus"] == s else 0)
    m.p_block_cap = Param(gens, m.s_blocks, doc="Capacidad de cada bloque [MW]",
                          initialize=lambda _, g, b: G.loc[g, b])
    m.p_c1_cost = Param(gens, m.s_blocks, doc="Costo marginal del bloque [$/MWh]",
                        initialize=lambda _, g, b: data.c1_cost[g, b])
    m.p_su_cost = Param(gens, m.s_segments, doc="Costo de arranque del segmento [$]",
                        initialize=lambda _, g, j: data.su_cost[g, j])


def _add_network_parameters(m: ConcreteModel, data: Data) -> None:
    L, W = data.lines, data.wind

    m.line_capacity = Param(m.s_lines, initialize=lambda _, l: L.loc[l, "cap"],
                            doc="Capacidad de la línea [MW]")
    m.line_y = Param(m.s_lines, initialize=lambda _, l: L.loc[l, "admittance"],
                     doc="Admitancia de la línea")
    m.line_map = Param(
        m.s_lines, m.s_buses, doc="+1 barra origen, -1 barra destino",
        initialize=lambda _, l, s: 1 if L.loc[l, "from"] == s else -1 if L.loc[l, "to"] == s else 0)

    m.load_profile = Param(m.s_buses, m.s_periods, doc="Demanda [MW]",
                           initialize=lambda _, s, t: data.loads.loc[t, s])
    m.wind_profile = Param(m.s_wind, m.s_periods, doc="Disponibilidad eólica [MW]",
                           initialize=lambda _, w, t: W.loc[t, w])
    m.t_wind_map = Param(m.s_wind, m.s_buses, doc="1 si el parque está en la barra",
                         initialize=lambda _, w, s: 1 if W.loc["bus id", w] == s else 0)


def _add_bess_parameters(m: ConcreteModel, bess) -> None:
    B = bess
    m.p_bess_cap = Param(m.s_bess, initialize=B["Cap"].to_dict(), doc="Capacidad de energía [MWh]")
    m.p_soc_mt = Param(m.s_bess, initialize=B["socmt"].to_dict(), doc="SOC mínimo [p.u.]")
    m.p_bess_pd = Param(m.s_bess, initialize=B["pd"].to_dict(), doc="Potencia máx. descarga [MW]")
    m.p_bess_pc = Param(m.s_bess, initialize=B["pc"].to_dict(), doc="Potencia máx. carga [MW]")
    m.p_bess_soc_ini = Param(m.s_bess, initialize=B["soc0"].to_dict(), doc="SOC inicial [p.u.]")
    m.p_bess_efic = Param(m.s_bess, initialize=B["efic"].to_dict(), doc="Eficiencia de carga")
    m.p_bess_Cefid = Param(m.s_bess, initialize=(1 / B["efid"]).to_dict(),
                           doc="Inverso de la eficiencia de descarga")
    m.p_bess_loss = Param(m.s_bess, initialize=B["loss"].to_dict(), doc="Pérdida por periodo [p.u.]")
    m.t_bess_map = Param(m.s_bess, m.s_buses, doc="1 si la batería está en la barra",
                         initialize=lambda _, b, s: 1 if B.loc[b, "bus"] == s else 0)


# --------------------------------------------------------------------------
# Variables
# --------------------------------------------------------------------------
def _add_variables(m: ConcreteModel, opts: ModelOptions) -> None:
    T, G = m.s_periods, m.s_generators

    # Costos y despacho térmico
    m.v_c_aux = Var(T, within=NonNegativeReals, doc="Costo total del periodo [$]")
    m.v_c = Var(T, G, within=NonNegativeReals, doc="Costo del generador en el periodo [$]")
    m.v_g = Var(T, G, within=NonNegativeReals, doc="Generación [MW]")
    m.v_x = Var(T, G, within=Binary, doc="1 si el generador está encendido")
    m.v_y = Var(T, G, within=Binary, doc="1 si el generador arranca")
    m.v_z = Var(T, G, within=Binary, doc="1 si el generador se apaga")

    # Viento y demanda no atendida / excedente
    m.v_curt = Var(T, m.s_wind, within=NonNegativeReals, doc="Vertimiento eólico [MW]")
    m.v_ll = Var(T, m.s_buses, within=NonNegativeReals, doc="Demanda no atendida [MW]")
    m.v_sl = Var(T, m.s_buses, within=NonNegativeReals, doc="Exceso de generación (slack) [MW]")

    # Baterías
    m.v_bess_soc = Var(T, m.s_bess, within=NonNegativeReals, doc="Estado de carga [p.u.]")
    m.v_bess_pd = Var(T, m.s_bess, within=NonNegativeReals, doc="Descarga [MW]")
    m.v_bess_pc = Var(T, m.s_bess, within=NonNegativeReals, doc="Carga [MW]")

    # Red (solo si el modelo es multinodal)
    if not opts.uninodal:
        m.v_pf = Var(T, m.s_lines, within=Reals, doc="Flujo por la línea [MW]")
        m.v_theta = Var(T, m.s_buses, within=Reals, doc="Ángulo de la barra [rad]")
        m.v_theta[:, REF_BUS].fix(0)


# --------------------------------------------------------------------------
# Función objetivo y costos (E1 - E3)
# --------------------------------------------------------------------------
def _add_objective_and_costs(m: ConcreteModel) -> None:
    # E1: minimizar el costo total de los periodos
    m.e_obj = Objective(expr=sum(m.v_c_aux[t] for t in m.s_periods), sense=minimize)

    # E2: costo del periodo = térmico + penalización vertimiento + penalización ENS
    m.e_cost_aux = Constraint(m.s_periods, rule=lambda m, t:
        m.v_c_aux[t] == sum(m.v_c[t, i] for i in m.s_generators)
        + WS_PENALTY * sum(m.v_curt[t, w] for w in m.s_wind)
        + VOLL * sum(m.v_ll[t, s] + m.v_sl[t, s] for s in m.s_buses))

    # E3: costo del generador = fijo + marginal (bloque b1) + arranque (segmento j1)
    m.e_cost_sum = Constraint(m.s_periods, m.s_generators, rule=lambda m, t, i:
        m.v_c[t, i] == m.p_co_cost[i] * m.v_x[t, i]
        + m.p_c1_cost[i, "b1"] * m.v_g[t, i]
        + m.p_su_cost[i, "j1"] * m.v_y[t, i])


# --------------------------------------------------------------------------
# Compromiso de unidades (E4 - E10)
# --------------------------------------------------------------------------
def _add_commitment_constraints(m: ConcreteModel) -> None:
    T, G = m.s_periods, m.s_generators
    pos = {t: k + 1 for k, t in enumerate(T)}   # t1 -> 1, t2 -> 2, ...

    # E4: lógica de arranque / parada
    def startup_shutdown(m, t, i):
        prev = m.v_x[T.prev(t), i] if t != T.first() else m.p_init_onoff[i]
        return m.v_y[t, i] - m.v_z[t, i] == m.v_x[t, i] - prev
    m.e_startup_shutdown = Constraint(T, G, rule=startup_shutdown)

    # E5: no arrancar y parar a la vez
    m.e_no_sumil_susd = Constraint(T, G, rule=lambda m, t, i: m.v_y[t, i] + m.v_z[t, i] <= 1)

    # E6 y E7: límites de generación (mínimo técnico y suma de bloques)
    m.e_gen_min = Constraint(T, G, rule=lambda m, t, i: m.v_g[t, i] >= m.p_mt[i] * m.v_x[t, i])
    m.e_block_output = Constraint(T, G, rule=lambda m, t, i:
        m.v_g[t, i] <= sum(m.p_block_cap[i, b] for b in m.s_blocks) * m.v_x[t, i])

    # E8: mantener el estado inicial las horas que falten de tiempo mínimo
    def min_updown_1(m, t, i):
        if pos[t] <= m.p_l_up_min[i] + m.p_l_down_min[i]:
            return m.v_x[t, i] == m.p_init_onoff[i]
        return Constraint.Skip
    m.e_min_updown_1 = Constraint(T, G, rule=min_updown_1)

    # E9: tiempo mínimo encendido
    m.e_min_updown_2 = Constraint(T, G, rule=lambda m, t, i:
        sum(m.v_y[tt, i] for tt in T if pos[t] - m.p_tmg[i] + 1 <= pos[tt] <= pos[t]) <= m.v_x[t, i])

    # E10: tiempo mínimo apagado
    m.e_min_updown_3 = Constraint(T, G, rule=lambda m, t, i:
        sum(m.v_z[tt, i] for tt in T if pos[t] - m.p_tmfl[i] + 1 <= pos[tt] <= pos[t]) <= 1 - m.v_x[t, i])


# --------------------------------------------------------------------------
# Rampas (E11 - E12)
# --------------------------------------------------------------------------
def _add_ramp_constraints(m: ConcreteModel) -> None:
    T, G = m.s_periods, m.s_generators

    # E11: rampa de bajada
    def ramp_down(m, t, i):
        if t != T.first():
            return (m.v_g[t, i] - m.v_g[T.prev(t), i]
                    >= -m.p_gen_dr[i] * m.v_x[T.prev(t), i] - m.p_mt[i] * m.v_z[t, i])
        return m.v_g[t, i] - m.p_g_init[i] >= -(m.p_gen_dr[i] if m.p_g_init[i] else m.p_mt[i])
    m.e_ramp_limit_min = Constraint(T, G, rule=ramp_down)

    # E12: rampa de subida
    def ramp_up(m, t, i):
        prev = m.v_g[T.prev(t), i] if t != T.first() else m.p_g_init[i]
        return m.v_g[t, i] - prev <= m.p_gen_ur[i] * m.v_x[t, i] + m.p_mt[i] * m.v_y[t, i]
    m.e_ramp_limit_max = Constraint(T, G, rule=ramp_up)


# --------------------------------------------------------------------------
# Balance de potencia y viento (E13, E14, E18)
# --------------------------------------------------------------------------
def _add_balance_constraints(m: ConcreteModel, opts: ModelOptions) -> None:
    T = m.s_periods

    if opts.uninodal:
        # E14: balance del sistema completo (sin red)
        m.e_uninodal_balance = Constraint(T, rule=lambda m, t:
            sum(m.v_g[t, i] for i in m.s_generators)
            + sum(m.wind_profile[w, t] - m.v_curt[t, w] for w in m.s_wind)
            + sum(m.v_bess_pd[t, b] - m.v_bess_pc[t, b] for b in m.s_bess)
            == sum(m.load_profile[s, t] - m.v_ll[t, s] + m.v_sl[t, s] for s in m.s_buses))
    else:
        # E13: balance nodal en cada barra
        def power_balance(m, t, s):
            return (sum(m.v_g[t, i] for i in m.s_generators if m.t_gen_map[i, s])
                    + sum(m.wind_profile[w, t] - m.v_curt[t, w] for w in m.s_wind if m.t_wind_map[w, s])
                    - sum(m.v_pf[t, l] * m.line_map[l, s] for l in m.s_lines if m.line_map[l, s] != 0)
                    + sum(m.v_bess_pd[t, b] - m.v_bess_pc[t, b] for b in m.s_bess if m.t_bess_map[b, s])
                    == m.load_profile[s, t] - m.v_ll[t, s] + m.v_sl[t, s])
        m.e_power_balance = Constraint(T, m.s_buses, rule=power_balance)

    # E18: no se puede verter más viento del disponible
    m.e_curt_cons = Constraint(T, m.s_wind, rule=lambda m, t, w: m.v_curt[t, w] <= m.wind_profile[w, t])


# --------------------------------------------------------------------------
# Red de transmisión: flujo DC (E15 - E17)
# --------------------------------------------------------------------------
def _add_network_constraints(m: ConcreteModel) -> None:
    T, L, S = m.s_periods, m.s_lines, m.s_buses

    # E15: flujo DC = admitancia * diferencia de ángulos
    m.e_line_flow = Constraint(T, L, rule=lambda m, t, l:
        m.v_pf[t, l] == m.line_y[l] * sum(m.v_theta[t, s] * m.line_map[l, s]
                                          for s in S if m.line_map[l, s] != 0))
    # E16: límites térmicos de la línea
    m.e_line_capacity_min = Constraint(T, L, rule=lambda m, t, l: m.v_pf[t, l] >= -m.line_capacity[l])
    m.e_line_capacity_max = Constraint(T, L, rule=lambda m, t, l: m.v_pf[t, l] <= m.line_capacity[l])
    # E17: límites de los ángulos
    m.e_voltage_angles_min = Constraint(T, S, rule=lambda m, t, s: m.v_theta[t, s] >= -pi)
    m.e_voltage_angles_max = Constraint(T, S, rule=lambda m, t, s: m.v_theta[t, s] <= pi)


# --------------------------------------------------------------------------
# Baterías (E19 - E24)
# --------------------------------------------------------------------------
def _add_bess_constraints(m: ConcreteModel, opts: ModelOptions) -> None:
    T, B = m.s_periods, m.s_bess
    if len(B) == 0:
        return

    # E19: dinámica del estado de carga (SOC, en p.u. de la capacidad)
    def bess_storage(m, t, b):
        prev = m.v_bess_soc[T.prev(t), b] if t != T.first() else m.p_bess_soc_ini[b]
        return (m.v_bess_soc[t, b] == prev * (1 - m.p_bess_loss[b])
                + m.p_bess_efic[b] * m.v_bess_pc[t, b] / m.p_bess_cap[b]
                - m.p_bess_Cefid[b] * m.v_bess_pd[t, b] / m.p_bess_cap[b])
    m.e_bess_storage = Constraint(T, B, rule=bess_storage)

    # E20 y E21: límites del SOC
    m.e_min_bess_soc = Constraint(T, B, rule=lambda m, t, b: m.v_bess_soc[t, b] >= m.p_soc_mt[b])
    m.e_max_bess_soc = Constraint(T, B, rule=lambda m, t, b: m.v_bess_soc[t, b] <= 1)

    # E22 y E23: límites de potencia de carga y descarga
    charge_cap = m.p_bess_pc if opts.charge_limit == "pc" else m.p_bess_pd
    m.e_max_bess_charge = Constraint(T, B, rule=lambda m, t, b: m.v_bess_pc[t, b] <= charge_cap[b])
    m.e_max_bess_discharge = Constraint(T, B, rule=lambda m, t, b: m.v_bess_pd[t, b] <= m.p_bess_pd[b])

    # E24 (opcional): no terminar el día con menos energía de la que se empezó
    if opts.terminal_soc:
        m.e_terminal_soc = Constraint(B, rule=lambda m, b:
            m.v_bess_soc[T.last(), b] >= m.p_bess_soc_ini[b])
