"""
Configuración global del proyecto.

Aquí viven las constantes del problema (penalizaciones, barra de referencia,
horizonte) y la regla del profesor para calcular la capacidad inicial de las
baterías a partir de la cédula.
"""
from __future__ import annotations

import re
from pathlib import Path

# --------------------------------------------------------------------------
# Rutas
# --------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT_DIR / "data" / "input_UC_IEEE24.xlsx"
RESULTS_DIR = ROOT_DIR / "results"

# --------------------------------------------------------------------------
# Parámetros del problema (mismos valores que bess.py del profesor)
# --------------------------------------------------------------------------
WS_PENALTY: float = 10_000     # $/MWh  penalización por vertimiento eólico
VOLL: float = 500_000          # $/MWh  valor de la energía no suministrada
REF_BUS: str = "s101"          # barra de referencia angular (theta = 0)
N_PERIODS: int = 24            # horizonte de optimización (horas)

# --------------------------------------------------------------------------
# Parámetros del experimento de la tarea (punto 2.1)
# --------------------------------------------------------------------------
TARGET_RATIO: float = 0.5      # objetivo: FO <= 50 % de la FO sin baterías
CAPACITY_STEP_MWH: float = 250.0   # incremento del barrido de capacidad
CAPACITY_TOL_MWH: float = 10.0     # precisión de la capacidad final (bisección)


def initial_capacity_from_cedula(cedula: str | int) -> int:
    """Capacidad inicial [MWh] = suma de las ternas de dígitos de la cédula.

    Las ternas se toman de derecha a izquierda. Ejemplo del profesor::

        1'234'500'222  ->  222 + 500 + 234 + 001 = 957 MWh
    """
    digits = re.sub(r"\D", "", str(cedula))
    if not digits:
        raise ValueError("La cédula debe contener al menos un dígito.")
    ternas = [digits[max(0, i - 3):i] for i in range(len(digits), 0, -3)]
    return sum(int(t) for t in ternas)
