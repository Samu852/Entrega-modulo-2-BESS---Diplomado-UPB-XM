# Tarea Módulo 2 — Unit Commitment IEEE-24 con baterías (BESS)

Diplomado UPB–XM, curso de optimización aplicada. Modelo en Pyomo, resuelto con HiGHS.

Resuelve los puntos de `homework.md`:

| Punto | Qué hace | Salida |
|---|---|---|
| 1 | Documentación del modelo (conjuntos, parámetros, variables, ecuaciones) | `docs/Documentacion_modelo_BESS.docx` (y `docs/modelo_bess.md`) |
| 2.1 | Parte de la capacidad inicial (suma de ternas de la cédula) y la aumenta hasta que la FO sea la mitad de la FO sin baterías | `results/fig_2_1_capacidad_vs_FO.png` |
| 2.2 | Demanda original vs demanda con baterías (demanda + carga − descarga) | `results/fig_2_2_demanda_original_vs_con_BESS.png` |
| 2.3 | Con la capacidad de 2.1, corre con y sin red y compara la FO | `results/fig_2_3_con_y_sin_red.png` |

El análisis de los resultados está en `docs/Analisis_resultados_BESS.docx`.

## Instalación

```bash
pip install -r requirements.txt
```

Requiere Python 3.10+. HiGHS se instala con `highspy` (no hace falta instalar nada más).

## Uso

```bash
python main.py --cedula "001 036 450 633"     # capacidad inicial = suma de ternas
python main.py --capacidad 1120               # o directamente en MWh
```

Opciones útiles:

| Opción | Significado | Por defecto |
|---|---|---|
| `--paso` | Incremento del barrido de capacidad [MWh] | 250 |
| `--tol` | Precisión de la capacidad final [MWh] | 10 |
| `--gap` / `--gap-red` | MIP gap del barrido / de la comparación con y sin red | 1e-4 / 1e-5 |
| `--carga-original` | Reproduce el `bess.py` del profesor (carga limitada con `pd`) | apagado |
| `--soc-final` | Extensión: exige SOC final ≥ SOC inicial (E24) | apagado |
| `--potencia-fija` | Solo escala la energía; la potencia `pd`/`pc` no cambia | apagado |
| `--salida` | Carpeta de resultados | `results/` |

Una corrida completa tarda unos 3 a 4 minutos (la mayor parte es el caso con red y sin baterías con gap 1e-5).

## Estructura

```
main.py                  Punto de entrada: corre 2.1, 2.2 y 2.3 y guarda todo
bess_uc/
  config.py              Constantes (penalizaciones, barra de referencia) y regla de la cédula
  data.py                Lectura del Excel (equivalente al digestor.py del curso)
  model.py               Modelo Pyomo, ecuaciones numeradas E1–E24
  solver.py              Llamado a HiGHS con manejo del estado de la solución
  results.py             Indicadores y series horarias de una solución
  experiments.py         Barrido de capacidad (2.1) y comparación con/sin red (2.3)
  plots.py               Gráficas
  report.py              Excel y resumen en Markdown
data/input_UC_IEEE24.xlsx   Datos de entrada
docs/modelo_bess.md         Documentación del modelo
results/                    Salidas de la corrida
```

## Resultados que genera `results/`

`resultados.xlsx` (parámetros, barrido, series horarias, comparación con/sin red), `resumen.md`, tres figuras PNG y los CSV
`barrido_capacidad.csv`, `comparacion_red.csv`, `horario_con_BESS.csv`.

## Qué cambia respecto a `bess.py` del curso

1. El modelo se construye en `build_model()`, para poder resolverlo muchas veces con distinta capacidad o con/sin red.
2. **Se corrige la restricción de carga máxima** (E22): el original usaba la potencia de descarga `p_bess_pd`; aquí usa `p_bess_pc`.
   `--carga-original` reproduce el comportamiento del profesor.
3. La capacidad de las 10 baterías se escala con el mismo factor, y `pd` y `pc` también (relación potencia/energía constante).
4. Se quitó la variable `v_suc` (declarada pero sin uso) y la escritura del `.lp`. En el modelo sin red no se crean las variables de flujo ni de ángulo.
5. Se agregó un diagnóstico de validez: cuántas baterías-hora cargan y descargan a la vez.

El detalle completo está en `docs/modelo_bess.md`, sección 6.
