"""
Lectura de datos del Excel (equivalente al `digestor.py` del curso).

La clase `Data` solo *lee y organiza* información: no contiene lógica de
optimización. Además ofrece `scaled_bess()`, que devuelve la tabla de baterías
escalada a una capacidad total deseada sin modificar los datos originales.
"""
from __future__ import annotations

from pathlib import Path

from pandas import DataFrame, ExcelFile

from .config import DATA_PATH, N_PERIODS


class Data:
    """Contenedor de los datos de entrada del caso IEEE-24 con BESS."""

    N_BLOCKS = 3      # bloques de costo marginal (b1..b3)
    N_SEGMENTS = 8    # segmentos de costo de arranque (j1..j8)

    def __init__(self, xlsx_path: Path = DATA_PATH, max_periods: int = N_PERIODS):
        xls = ExcelFile(xlsx_path)
        self.lines: DataFrame = xls.parse("line_admittance", index_col=0)
        self.generators: DataFrame = xls.parse("gen", index_col=0)
        self.gen_cost: DataFrame = xls.parse("gen_cost", index_col=0)
        self.gen_su_cost: DataFrame = xls.parse("gen_su_cost", index_col=0)
        self.loads: DataFrame = xls.parse("load", index_col=0)
        self.wind: DataFrame = xls.parse("wind", index_col=0)
        self.bess_base: DataFrame = xls.parse("bess", index_col=0)

        # ---- Conjuntos -------------------------------------------------
        self.s_lines: list = list(self.lines.index)
        self.s_generators: list = list(self.generators.index)
        self.s_blocks: list = [f"b{i}" for i in range(1, self.N_BLOCKS + 1)]
        self.s_segments: list = [f"j{i}" for i in range(1, self.N_SEGMENTS + 1)]
        self.s_bus: list = list(self.loads.columns)
        self.s_wind: list = list(self.wind.columns)
        self.s_periods: list = list(self.loads.index[:max_periods])
        self.s_bess: list = list(self.bess_base.index)

        # ---- Costos en diccionarios {(gen, bloque|segmento): costo} -----
        self.c1_cost: dict = self._to_dict(self.gen_cost, "block")
        self.su_cost: dict = self._to_dict(self.gen_su_cost, "segment")

        self._validate()

    # ------------------------------------------------------------------
    @staticmethod
    def _to_dict(df: DataFrame, key_col: str) -> dict:
        return {(g, k): c for g, k, c in zip(df.index, df[key_col], df["Cost"])}

    def _validate(self) -> None:
        """Verifica que el Excel tenga las columnas que el modelo espera."""
        for col in (*self.s_blocks, *self.s_segments):
            assert col in self.generators.columns, f"Falta la columna '{col}' en 'gen'"
        for col in ("bus", "Cap", "socmt", "pd", "pc", "soc0", "efic", "efid", "loss"):
            assert col in self.bess_base.columns, f"Falta la columna '{col}' en 'bess'"
        assert "bus id" in self.wind.index, "Falta la fila 'bus id' en la hoja 'wind'"

    # ------------------------------------------------------------------
    @property
    def base_bess_capacity(self) -> float:
        """Capacidad total de las baterías en los datos originales [MWh]."""
        return float(self.bess_base["Cap"].sum())

    def scaled_bess(self, total_mwh: float, scale_power: bool = True) -> DataFrame:
        """Tabla `bess` escalada para que la capacidad total sume `total_mwh`.

        Las 10 baterías conservan su reparto relativo (factor k = total / base).
        Si `scale_power` es True, `pd` y `pc` se escalan con el mismo factor,
        de modo que se mantiene la relación potencia/energía de los datos
        (pd = 0,10·Cap ; pc = 0,11·Cap). Si es False, solo crece la energía.
        """
        k = total_mwh / self.base_bess_capacity
        bess = self.bess_base.copy()
        cols = ("Cap", "pd", "pc") if scale_power else ("Cap",)
        for col in cols:
            bess[col] = self.bess_base[col] * k
        return bess


if __name__ == "__main__":
    d = Data()
    print(f"Generadores: {len(d.s_generators)} | Barras: {len(d.s_bus)} | "
          f"Líneas: {len(d.s_lines)} | Eólicas: {len(d.s_wind)} | "
          f"Baterías: {len(d.s_bess)} ({d.base_bess_capacity:.0f} MWh) | "
          f"Periodos: {len(d.s_periods)}")
