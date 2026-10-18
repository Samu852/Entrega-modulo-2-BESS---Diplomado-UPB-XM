# Resumen de resultados

## Parámetros de la corrida

- **Capacidad inicial C0 [MWh]**: 1,120
- **Cédula**: 001 036 450 633
- **Horizonte [h]**: 24
- **Paso del barrido [MWh]**: 250.0
- **Tolerancia [MWh]**: 10.0
- **Objetivo [fracción de FO base]**: 0.5
- **MIP gap barrido / red**: 0.0001 / 0.0001
- **Límite de carga**: pd (original)
- **Potencia escalada con la capacidad**: True
- **SOC final >= inicial**: False
- **Penalización vertimiento [$/MWh]**: 10,000
- **VOLL [$/MWh]**: 500,000

## 2.1 Capacidad instalada vs función objetivo

- FO sin baterías: **43,531,806 $**
- Objetivo (50 %): **21,765,903 $**
- Capacidad que cumple el objetivo: **4,541.9 MWh** (FO = 21,742,461 $, 49.95 % de la base)

| Capacidad [MWh] | FO [$] | FO / FO base | Vertimiento [MWh] | Carga [MWh] | Descarga [MWh] | dFO/dC [$/MWh] |
|---:|---:|---:|---:|---:|---:|---:|
| 0.0 | 43,531,806 | 100.00 % | 4,324.5 | 0.0 | 0.0 |  |
| 1,120.0 | 36,805,636 | 84.55 % | 3,652.5 | 1,310.1 | 547.4 | -6,006 |
| 1,370.0 | 35,304,596 | 81.10 % | 3,502.5 | 1,774.4 | 788.4 | -6,004 |
| 1,620.0 | 34,023,686 | 78.16 % | 3,374.5 | 2,003.4 | 862.7 | -5,124 |
| 1,870.0 | 32,772,801 | 75.28 % | 3,249.5 | 2,265.4 | 966.7 | -5,004 |
| 2,120.0 | 31,520,855 | 72.41 % | 3,124.5 | 2,366.0 | 974.5 | -5,008 |
| 2,370.0 | 30,434,267 | 69.91 % | 3,015.8 | 2,660.4 | 1,102.8 | -4,346 |
| 2,620.0 | 29,433,774 | 67.61 % | 2,915.8 | 2,825.0 | 1,161.6 | -4,002 |
| 2,870.0 | 28,433,314 | 65.32 % | 2,815.8 | 2,978.2 | 1,217.0 | -4,002 |
| 3,120.0 | 27,432,532 | 63.02 % | 2,715.8 | 3,124.5 | 1,265.4 | -4,003 |
| 3,370.0 | 26,432,432 | 60.72 % | 2,615.8 | 3,151.0 | 1,238.4 | -4,000 |
| 3,620.0 | 25,432,025 | 58.42 % | 2,515.8 | 3,298.2 | 1,288.1 | -4,002 |
| 3,870.0 | 24,431,866 | 56.12 % | 2,415.8 | 3,575.7 | 1,432.9 | -4,001 |
| 4,120.0 | 23,431,575 | 53.83 % | 2,315.8 | 3,726.7 | 1,485.7 | -4,001 |
| 4,370.0 | 22,430,613 | 51.53 % | 2,215.8 | 3,753.5 | 1,442.9 | -4,004 |
| 4,495.0 | 21,930,498 | 50.38 % | 2,165.8 | 3,815.0 | 1,459.2 | -4,001 |
| 4,526.2 | 21,805,472 | 50.09 % | 2,153.3 | 3,829.7 | 1,462.8 | -4,001 |
| 4,534.1 | 21,773,718 | 50.02 % | 2,150.2 | 3,810.3 | 1,442.6 | -4,064 |
| 4,541.9 | 21,742,461 | 49.95 % | 2,147.1 | 3,813.7 | 1,443.2 | -4,001 |
| 4,557.5 | 21,679,947 | 49.80 % | 2,140.8 | 3,820.4 | 1,444.4 | -4,001 |
| 4,620.0 | 21,429,892 | 49.23 % | 2,115.8 | 3,846.3 | 1,448.6 | -4,001 |

## 2.2 Demanda original vs demanda con baterías

- Capacidad: 4,541.9 MWh
- Energía cargada: 3,813.7 MWh | descargada: 1,443.2 MWh
- Horas con carga > 0: 21 | con descarga > 0: 10
- Pico de demanda original: 2,513.2 MW | con baterías: 2,741.2 MW
- Vertimiento sin baterías: 4,324.5 MWh | con baterías: 2,147.1 MWh
- Energía almacenada al inicio: 1,492.2 MWh | al final: 2,089.2 MWh
- Baterías-hora con carga y descarga simultánea (diagnóstico): 0

## 2.3 Con y sin red

| Caso | FO [$] | Vertimiento [MWh] | Carga máx. línea [%] | Líneas-hora congestionadas |
|---|---:|---:|---:|---:|
| con red, sin BESS | 43,531,805.56 | 4,324.5 | 92.2 | 0 |
| sin red, sin BESS | 43,531,748.09 | 4,324.5 | — | — |
| con red, BESS 4,542 MWh | 21,742,461.15 | 2,147.1 | 89.6 | 0 |
| sin red, BESS 4,542 MWh | 21,743,813.52 | 2,147.1 | — | — |

- Sin baterías: FO(con red) − FO(sin red) = **57.48 $** (0.00013 %)
- Con baterías: FO(con red) − FO(sin red) = **-1,352.37 $** (-0.00622 %)
