"""
Exportación de resultados: libro de Excel y resumen en Markdown.
"""
from __future__ import annotations

from pathlib import Path

from pandas import DataFrame, ExcelWriter

from .experiments import CaseResult, SweepResult


def export_excel(path: Path, params: dict, sweep: SweepResult, final: CaseResult,
                 base: CaseResult, grid: DataFrame) -> Path:
    """Un libro con todo lo necesario para el documento de análisis."""
    with ExcelWriter(path, engine="openpyxl") as xw:
        DataFrame({"parametro": list(params), "valor": [str(v) for v in params.values()]}).to_excel(
            xw, sheet_name="parametros", index=False)
        sweep.table.to_excel(xw, sheet_name="2.1_barrido_capacidad", index=False)
        final.hourly.to_excel(xw, sheet_name="2.2_horario_con_BESS", index_label="periodo")
        base.hourly.to_excel(xw, sheet_name="2.2_horario_sin_BESS", index_label="periodo")
        final.bess.to_excel(xw, sheet_name="2.2_por_bateria", index=False)
        grid.to_excel(xw, sheet_name="2.3_con_y_sin_red", index=False)
        for ws in xw.book.worksheets:                       # ancho de columnas legible
            for col in ws.columns:
                width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
                ws.column_dimensions[col[0].column_letter].width = min(max(12, width + 2), 40)
    return path


def write_summary(path: Path, params: dict, sweep: SweepResult, final: CaseResult,
                  base: CaseResult, grid: DataFrame) -> Path:
    """Resumen en Markdown con las cifras clave (insumo directo del documento de análisis)."""
    t = sweep.table
    h, hb = final.hourly, base.hourly
    f = final.summary
    L: list[str] = ["# Resumen de resultados", ""]

    L += ["## Parámetros de la corrida", ""]
    L += [f"- **{k}**: {v}" for k, v in params.items()]

    L += ["", "## 2.1 Capacidad instalada vs función objetivo", "",
          f"- FO sin baterías: **{sweep.base_fo:,.0f} $**",
          f"- Objetivo (50 %): **{sweep.target_fo:,.0f} $**"]
    if sweep.reached:
        L += [f"- Capacidad que cumple el objetivo: **{sweep.final_capacity:,.1f} MWh** "
              f"(FO = {f['FO']:,.0f} $, {100 * f['FO'] / sweep.base_fo:.2f} % de la base)"]
    else:
        L += ["- **No se alcanzó el objetivo** dentro del rango explorado."]
    L += ["", "| Capacidad [MWh] | FO [$] | FO / FO base | Vertimiento [MWh] | Carga [MWh] | Descarga [MWh] | dFO/dC [$/MWh] |",
          "|---:|---:|---:|---:|---:|---:|---:|"]
    for _, r in t.iterrows():
        d = "" if r["dFO_dCap"] != r["dFO_dCap"] else f"{r['dFO_dCap']:,.0f}"
        L.append(f"| {r['capacidad_MWh']:,.1f} | {r['FO']:,.0f} | {r['FO_pct_base']:.2f} % | "
                 f"{r['vertimiento_MWh']:,.1f} | {r['carga_MWh']:,.1f} | {r['descarga_MWh']:,.1f} | {d} |")

    L += ["", "## 2.2 Demanda original vs demanda con baterías", "",
          f"- Capacidad: {final.options.bess_capacity_mwh:,.1f} MWh",
          f"- Energía cargada: {f['carga_MWh']:,.1f} MWh | descargada: {f['descarga_MWh']:,.1f} MWh",
          f"- Horas con carga > 0: {int((h['carga_MW'] > 1e-6).sum())} | con descarga > 0: {int((h['descarga_MW'] > 1e-6).sum())}",
          f"- Pico de demanda original: {h['demanda_MW'].max():,.1f} MW | con baterías: {h['demanda_con_BESS_MW'].max():,.1f} MW",
          f"- Vertimiento sin baterías: {hb['vertimiento_MW'].sum():,.1f} MWh | con baterías: {h['vertimiento_MW'].sum():,.1f} MWh",
          f"- Energía almacenada al inicio: {f['energia_inicial_MWh']:,.1f} MWh | al final: {f['energia_final_MWh']:,.1f} MWh",
          f"- Baterías-hora con carga y descarga simultánea (diagnóstico): {int(f['bess_carga_y_descarga_h'])}",
          "- SOC máximo alcanzado por batería: " + ", ".join(
              f"{r.bateria} {r.soc_max_pu:.2f}" for r in final.bess.itertuples())]

    L += ["", "## 2.3 Con y sin red", "",
          "| Caso | FO [$] | Vertimiento [MWh] | Carga máx. línea [%] | Líneas-hora congestionadas |",
          "|---|---:|---:|---:|---:|"]
    for _, r in grid.iterrows():
        mx = "—" if r["max_carga_linea_pct"] != r["max_carga_linea_pct"] else f"{r['max_carga_linea_pct']:.1f}"
        cg = "—" if r["lineas_congestionadas_h"] != r["lineas_congestionadas_h"] else f"{int(r['lineas_congestionadas_h'])}"
        L.append(f"| {r['caso']} | {r['FO']:,.2f} | {r['vertimiento_MWh']:,.1f} | {mx} | {cg} |")
    L += [""]
    for _, r in grid[grid["con_red"]].iterrows():
        L.append(f"- {'Con' if r['con_BESS'] else 'Sin'} baterías: FO(con red) − FO(sin red) = "
                 f"**{r['dFO_vs_sin_red']:,.2f} $** ({r['dFO_vs_sin_red_pct']:.5f} %)")

    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return path
