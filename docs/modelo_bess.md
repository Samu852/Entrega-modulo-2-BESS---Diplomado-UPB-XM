# Modelo BESS: Unit Commitment IEEE-24 con almacenamiento en baterías

Documentación del modelo implementado en `bess_uc/model.py` (punto 1 de la tarea).
Es el modelo `C03/bess.py` del curso, con la misma nomenclatura (`s_` conjuntos, `p_`/`t_` parámetros,
`v_` variables, `e_` ecuaciones). Cada ecuación lleva un número (E1–E24) que coincide con los comentarios del código.

**Horizonte:** 24 horas. **Resolución:** MILP con HiGHS (vía Pyomo). **Red:** flujo DC. **Sistema:** IEEE-24 barras, 32 generadores térmicos, 9 parques eólicos, 10 baterías.

---

## 1. Conjuntos

| Símbolo | Nombre en código | Elementos | Descripción |
|---|---|---|---|
| $T$ | `s_periods` | $t_1 \dots t_{24}$ | Periodos (horas), ordenado |
| $I$ | `s_generators` | $i_1 \dots i_{32}$ | Generadores térmicos |
| $S$ | `s_buses` | $s_{101} \dots s_{124}$ | Barras |
| $L$ | `s_lines` | $l_1 \dots l_{38}$ | Líneas de transmisión |
| $W$ | `s_wind` | $w_1 \dots w_9$ | Parques eólicos |
| $B$ | `s_bess` | $q_1 \dots q_{10}$ | Baterías (BESS) |
| $K$ | `s_blocks` | $b_1, b_2, b_3$ | Bloques de capacidad de la curva de generación |
| $J$ | `s_segments` | $j_1 \dots j_8$ | Segmentos del costo de arranque |

Subconjuntos de ubicación: $I(s)$, $W(s)$ y $B(s)$ son los generadores, parques eólicos y baterías conectados a la barra $s$
(en código: `t_gen_map`, `t_wind_map`, `t_bess_map`).

---

## 2. Parámetros

### 2.1 Generadores (hoja `gen`, `gen_cost`, `gen_su_cost`)

| Símbolo | Código | Unidad | Descripción |
|---|---|---|---|
| $P^{blk}_{i,k}$ | `p_block_cap` | MW | Capacidad del bloque $k$ del generador $i$ |
| $P^{min}_i$ | `p_mt` | MW | Mínimo técnico |
| $UR_i,\; DR_i$ | `p_gen_ur`, `p_gen_dr` | MW/h | Rampa máxima de subida y de bajada |
| $TMG_i$ | `p_tmg` | h | Tiempo mínimo encendido |
| $TMFL_i$ | `p_tmfl` | h | Tiempo mínimo apagado |
| $cON_i,\; cOFF_i$ | `p_count_on`, `p_count_off` | h | Horas que lleva encendido / apagado al inicio |
| $G^0_i$ | `p_g_init` | MW | Generación inicial |
| $u^0_i$ | `p_init_onoff` | 0/1 | Estado inicial: 1 si $cON_i>0$ y $G^0_i>0$ |
| $L^{up}_i$ | `p_l_up_min` | h | Horas iniciales que debe seguir encendido: $\min\{24,\max(0,TMG_i-cON_i)\}$ si $u^0_i=1$, si no 0 |
| $L^{dn}_i$ | `p_l_down_min` | h | Horas iniciales que debe seguir apagado: $\min\{24,\max(0,TMFL_i+cOFF_i)\}$ si $u^0_i=0$, si no 0 |
| $C^0_i$ | `p_co_cost` | $/h | Costo fijo de operación (generador encendido) |
| $c_i$ | `p_c1_cost[i,b1]` | $/MWh | Costo marginal (bloque $b_1$) |
| $SU_i$ | `p_su_cost[i,j1]` | $ | Costo de arranque (segmento $j_1$) |

### 2.2 Red, demanda y viento (hojas `line_admittance`, `load`, `wind`)

| Símbolo | Código | Unidad | Descripción |
|---|---|---|---|
| $F^{max}_l$ | `line_capacity` | MW | Capacidad de la línea |
| $Y_l$ | `line_y` | — | Admitancia de la línea |
| $A_{l,s}$ | `line_map` | — | $+1$ si $s$ es la barra origen de $l$, $-1$ si es la destino, 0 si no |
| $D_{s,t}$ | `load_profile` | MW | Demanda de la barra $s$ en el periodo $t$ |
| $W^{av}_{w,t}$ | `wind_profile` | MW | Potencia eólica disponible |

### 2.3 Baterías (hoja `bess`)

| Símbolo | Código | Unidad | Descripción |
|---|---|---|---|
| $E_b$ | `p_bess_cap` | MWh | Capacidad de energía |
| $SOC^{min}_b$ | `p_soc_mt` | p.u. | Estado de carga mínimo |
| $SOC^0_b$ | `p_bess_soc_ini` | p.u. | Estado de carga inicial |
| $PD_b$ | `p_bess_pd` | MW | Potencia máxima de descarga |
| $PC_b$ | `p_bess_pc` | MW | Potencia máxima de carga |
| $\eta^c_b$ | `p_bess_efic` | p.u. | Eficiencia de carga |
| $1/\eta^d_b$ | `p_bess_Cefid` | p.u. | Inverso de la eficiencia de descarga |
| $\lambda_b$ | `p_bess_loss` | p.u./h | Pérdida de energía almacenada por periodo |

### 2.4 Constantes globales (`bess_uc/config.py`)

| Símbolo | Valor | Descripción |
|---|---|---|
| $\pi^{w}$ | 10 000 $/MWh | Penalización por vertimiento eólico (`WS_PENALTY`) |
| $VOLL$ | 500 000 $/MWh | Valor de la energía no suministrada y del exceso (`VOLL`) |
| $s^{ref}$ | `s101` | Barra de referencia angular (`REF_BUS`) |

> **Escalamiento de la capacidad (punto 2).** Para variar la capacidad total instalada $E^{tot}$ las 10 baterías se escalan con el mismo
> factor $k = E^{tot}/615$ (615 MWh es la capacidad de los datos): $E_b \leftarrow k\,E_b$, $PD_b \leftarrow k\,PD_b$, $PC_b \leftarrow k\,PC_b$.
> Así se conserva el reparto entre barras y la relación potencia/energía de los datos ($PD_b = 0{,}10\,E_b$ y $PC_b = 0{,}11\,E_b$).

---

## 3. Variables

| Símbolo | Código | Dominio | Unidad | Descripción |
|---|---|---|---|---|
| $C^{aux}_t$ | `v_c_aux[t]` | $\ge 0$ | $ | Costo total del periodo |
| $C_{t,i}$ | `v_c[t,i]` | $\ge 0$ | $ | Costo del generador $i$ en el periodo $t$ |
| $g_{t,i}$ | `v_g[t,i]` | $\ge 0$ | MW | Generación térmica |
| $x_{t,i}$ | `v_x[t,i]` | binaria | — | 1 si el generador está encendido |
| $y_{t,i}$ | `v_y[t,i]` | binaria | — | 1 si el generador arranca en $t$ |
| $z_{t,i}$ | `v_z[t,i]` | binaria | — | 1 si el generador se apaga en $t$ |
| $f_{t,l}$ | `v_pf[t,l]` | libre | MW | Flujo por la línea (solo con red) |
| $\theta_{t,s}$ | `v_theta[t,s]` | libre | rad | Ángulo de la barra (solo con red) |
| $cu_{t,w}$ | `v_curt[t,w]` | $\ge 0$ | MW | Vertimiento eólico |
| $ll_{t,s}$ | `v_ll[t,s]` | $\ge 0$ | MW | Demanda no atendida |
| $sl_{t,s}$ | `v_sl[t,s]` | $\ge 0$ | MW | Exceso de generación (slack) |
| $soc_{t,b}$ | `v_bess_soc[t,b]` | $\ge 0$ | p.u. | Estado de carga de la batería |
| $pc_{t,b}$ | `v_bess_pc[t,b]` | $\ge 0$ | MW | Potencia de carga |
| $pd_{t,b}$ | `v_bess_pd[t,b]` | $\ge 0$ | MW | Potencia de descarga |

---

## 4. Ecuaciones

### Función objetivo y costos

**E1 — Función objetivo** (`e_obj`): minimizar el costo total del horizonte.

$$\min \; \sum_{t \in T} C^{aux}_t$$

**E2 — Costo del periodo** (`e_cost_aux`): costo térmico + penalización por vertimiento + penalización por energía no suministrada o en exceso.

$$C^{aux}_t = \sum_{i \in I} C_{t,i} + \pi^{w} \sum_{w \in W} cu_{t,w} + VOLL \sum_{s \in S} \left( ll_{t,s} + sl_{t,s} \right) \qquad \forall t$$

**E3 — Costo del generador** (`e_cost_sum`): costo fijo + costo marginal + costo de arranque.

$$C_{t,i} = C^0_i\, x_{t,i} + c_i\, g_{t,i} + SU_i\, y_{t,i} \qquad \forall t, i$$

### Compromiso de unidades

**E4 — Lógica de arranque y parada** (`e_startup_shutdown`), con $x_{0,i} = u^0_i$:

$$y_{t,i} - z_{t,i} = x_{t,i} - x_{t-1,i} \qquad \forall t, i$$

**E5 — No arrancar y parar a la vez** (`e_no_sumil_susd`):

$$y_{t,i} + z_{t,i} \le 1 \qquad \forall t, i$$

**E6 — Mínimo técnico** (`e_gen_min`):

$$g_{t,i} \ge P^{min}_i\, x_{t,i} \qquad \forall t, i$$

**E7 — Capacidad máxima** (`e_block_output`), suma de los tres bloques:

$$g_{t,i} \le \Big( \sum_{k \in K} P^{blk}_{i,k} \Big)\, x_{t,i} \qquad \forall t, i$$

**E8 — Estado inicial obligado** (`e_min_updown_1`): las primeras horas se mantiene el estado inicial.

$$x_{t,i} = u^0_i \qquad \forall i,\; t \le L^{up}_i + L^{dn}_i$$

**E9 — Tiempo mínimo encendido** (`e_min_updown_2`):

$$\sum_{\tau = t - TMG_i + 1}^{t} y_{\tau,i} \le x_{t,i} \qquad \forall t, i$$

**E10 — Tiempo mínimo apagado** (`e_min_updown_3`):

$$\sum_{\tau = t - TMFL_i + 1}^{t} z_{\tau,i} \le 1 - x_{t,i} \qquad \forall t, i$$

(Las sumas solo incluyen periodos $\tau \ge 1$ dentro del horizonte.)

### Rampas

**E11 — Rampa de bajada** (`e_ramp_limit_min`):

$$g_{t,i} - g_{t-1,i} \ge -DR_i\, x_{t-1,i} - P^{min}_i\, z_{t,i} \qquad \forall t \ge 2,\; i$$

$$g_{1,i} - G^0_i \ge -\begin{cases} DR_i & \text{si } G^0_i > 0 \\ P^{min}_i & \text{si } G^0_i = 0 \end{cases}$$

**E12 — Rampa de subida** (`e_ramp_limit_max`), con $g_{0,i} = G^0_i$:

$$g_{t,i} - g_{t-1,i} \le UR_i\, x_{t,i} + P^{min}_i\, y_{t,i} \qquad \forall t, i$$

### Balance de potencia y viento

**E13 — Balance nodal** (`e_power_balance`, modelo con red): generación + eólica neta − flujo neto saliente + (descarga − carga) = demanda atendida.

$$\sum_{i \in I(s)} g_{t,i} + \sum_{w \in W(s)} \left( W^{av}_{w,t} - cu_{t,w} \right) - \sum_{l \in L} A_{l,s}\, f_{t,l} + \sum_{b \in B(s)} \left( pd_{t,b} - pc_{t,b} \right) = D_{s,t} - ll_{t,s} + sl_{t,s} \qquad \forall t, s$$

**E14 — Balance del sistema** (`e_uninodal_balance`, modelo **sin red**): mismo balance sumado sobre todas las barras (el flujo desaparece).

$$\sum_{i \in I} g_{t,i} + \sum_{w \in W} \left( W^{av}_{w,t} - cu_{t,w} \right) + \sum_{b \in B} \left( pd_{t,b} - pc_{t,b} \right) = \sum_{s \in S} \left( D_{s,t} - ll_{t,s} + sl_{t,s} \right) \qquad \forall t$$

**E18 — Vertimiento acotado** (`e_curt_cons`):

$$cu_{t,w} \le W^{av}_{w,t} \qquad \forall t, w$$

### Red de transmisión (flujo DC, solo en el modelo con red)

**E15 — Flujo DC** (`e_line_flow`):

$$f_{t,l} = Y_l \sum_{s \in S} A_{l,s}\, \theta_{t,s} \qquad \forall t, l$$

**E16 — Límite térmico de la línea** (`e_line_capacity_min/max`):

$$-F^{max}_l \le f_{t,l} \le F^{max}_l \qquad \forall t, l$$

**E17 — Límites de ángulo** (`e_voltage_angles_min/max`), con $\theta_{t,s^{ref}} = 0$:

$$-\pi \le \theta_{t,s} \le \pi \qquad \forall t, s$$

### Baterías (BESS)

**E19 — Dinámica del estado de carga** (`e_bess_storage`), con $soc_{0,b} = SOC^0_b$:

$$soc_{t,b} = (1 - \lambda_b)\, soc_{t-1,b} + \frac{\eta^c_b\, pc_{t,b}}{E_b} - \frac{pd_{t,b}}{\eta^d_b\, E_b} \qquad \forall t, b$$

**E20 y E21 — Límites del estado de carga** (`e_min_bess_soc`, `e_max_bess_soc`):

$$SOC^{min}_b \le soc_{t,b} \le 1 \qquad \forall t, b$$

**E22 — Potencia máxima de carga** (`e_max_bess_charge`):

$$pc_{t,b} \le PC_b \qquad \forall t, b$$

**E23 — Potencia máxima de descarga** (`e_max_bess_discharge`):

$$pd_{t,b} \le PD_b \qquad \forall t, b$$

**E24 — SOC final (opcional, extensión nuestra, desactivada por defecto)** (`e_terminal_soc`): no terminar el día con menos energía de la que se empezó.

$$soc_{24,b} \ge SOC^0_b \qquad \forall b$$

---

## 5. Cómo se obtienen los tres escenarios de la tarea

| Escenario | Qué cambia en el modelo |
|---|---|
| **Sin baterías** | $B = \emptyset$: no existen las variables ni las ecuaciones E19–E24 |
| **Sin red** (uninodal) | Se usa E14 en lugar de E13, y no existen $f$, $\theta$ ni E15–E17 |
| **Con red** | Se usa E13 y se incluyen E15–E17 |

---

## 6. Diferencias respecto a `bess.py` del curso y supuestos a tener presentes

1. **Corrección de E22.** El original limitaba la carga con la potencia de *descarga* (`p_bess_pd`); aquí se usa la de *carga* (`p_bess_pc`),
   que es el parámetro que corresponde. El original se reproduce con la opción `--carga-original`.
2. **Escalamiento de la potencia.** Al aumentar la capacidad, $PC_b$ y $PD_b$ crecen en la misma proporción que $E_b$ (ver 2.4).
3. **Curva de costos simplificada (heredada del original).** E3 usa solo el costo marginal del bloque $b_1$ y el segmento de arranque $j_1$;
   los bloques $b_2, b_3$ solo entran sumando su capacidad en E7.
4. **Carga y descarga simultáneas.** El modelo no incluye una binaria que lo impida (igual que el original). El código revisa el resultado y reporta
   cuántas baterías-hora cargan y descargan a la vez (`bess_carga_y_descarga_h`).
5. **Horizonte cerrado.** E24 está desactivada por defecto, por lo que las baterías pueden terminar el día con más o menos energía que al inicio.
6. **El vertimiento eólico se penaliza** ($\pi^w$ = 10 000 $/MWh), por lo que la función objetivo no es solo el costo térmico:
   incluye una penalización que domina el valor total.
